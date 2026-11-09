// Copyright 2026 The Paani Authors
// Use of this source code is governed by a GPL-3.0 license that can be
// found in the LICENSE file.

//! A C ABI shim over the Brave `adblock-rust` engine.
//!
//! The vendored crate is built without its `single-thread` feature, so the
//! engine is `Send` and `Sync`.  It is built on a background thread and then
//! used from the thread that owns the profile.

use adblock::lists::{FilterSet, ParseOptions};
use adblock::request::Request;
use adblock::resources::{MimeType, PermissionMask, Resource, ResourceType};
use adblock::Engine;

use std::ffi::{c_char, c_void, CString};
use std::slice;
use std::str;

/// The request is allowed.
const PAANI_ADBLOCK_ALLOW: i32 = 0;
/// The request is blocked by a filter rule.
const PAANI_ADBLOCK_BLOCK: i32 = 1;
/// The request could not be evaluated.
const PAANI_ADBLOCK_ERROR: i32 = -1;

/// A redirect stub, in the layout declared in paani_adblock_rust.h.
#[repr(C)]
pub struct PaaniRedirectResourceC {
    name: *const u8,
    name_len: usize,
    content: *const u8,
    content_len: usize,
    alias_ptrs: *const *const u8,
    alias_lens: *const usize,
    alias_count: usize,
}

/// Borrows a UTF-8 string that the caller keeps alive for the call.
///
/// # Safety
///
/// `ptr` must point to `len` readable bytes, or be null when `len` is zero.
unsafe fn str_from_raw<'a>(ptr: *const u8, len: usize) -> Option<&'a str> {
    if ptr.is_null() {
        return None;
    }
    let bytes = unsafe { slice::from_raw_parts(ptr, len) };
    str::from_utf8(bytes).ok()
}

/// Creates an engine from the given filter lists.
///
/// Returns a null pointer if no list could be used.
///
/// # Safety
///
/// `list_ptrs` and `list_lens` must each point to `list_count` readable
/// elements, and every list must stay alive for the duration of the call.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn paani_adblock_engine_create(
    list_ptrs: *const *const u8,
    list_lens: *const usize,
    list_count: usize,
) -> *mut c_void {
    if list_ptrs.is_null() || list_lens.is_null() || list_count == 0 {
        return std::ptr::null_mut();
    }

    let mut filter_set = FilterSet::new(false);
    for index in 0..list_count {
        let ptr = unsafe { *list_ptrs.add(index) };
        let len = unsafe { *list_lens.add(index) };
        let Some(text) = (unsafe { str_from_raw(ptr, len) }) else {
            continue;
        };
        filter_set.add_filter_list(text.to_owned(), ParseOptions::default());
    }

    let engine = Box::new(Engine::new_with_filter_set(filter_set));
    Box::into_raw(engine) as *mut c_void
}

/// Hands the redirect stubs to the engine.
///
/// `content` is the base64 of the stub payload. The MIME type is inferred from
/// the file name, exactly like uBlock Origin does. Returns the number of
/// resources the engine took, or -1 when it could not be used at all.
///
/// # Safety
///
/// `engine` must be a pointer returned by `paani_adblock_engine_create`, and
/// `resources` must point to `resource_count` readable descriptors whose
/// buffers stay alive for the duration of the call.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn paani_adblock_use_resources(
    engine: *mut c_void,
    resources: *const PaaniRedirectResourceC,
    resource_count: usize,
) -> i32 {
    if engine.is_null() || resources.is_null() {
        return PAANI_ADBLOCK_ERROR;
    }

    let mut items = Vec::with_capacity(resource_count);
    for index in 0..resource_count {
        let descriptor = unsafe { &*resources.add(index) };
        let Some(name) = (unsafe { str_from_raw(descriptor.name, descriptor.name_len) }) else {
            continue;
        };
        // The content is already base64, which is the form Resource stores.
        let Some(content) = (unsafe { str_from_raw(descriptor.content, descriptor.content_len) })
        else {
            continue;
        };

        let mut aliases = Vec::with_capacity(descriptor.alias_count);
        for alias_index in 0..descriptor.alias_count {
            let ptr = unsafe { *descriptor.alias_ptrs.add(alias_index) };
            let len = unsafe { *descriptor.alias_lens.add(alias_index) };
            if let Some(alias) = (unsafe { str_from_raw(ptr, len) }) {
                aliases.push(alias.to_string());
            }
        }

        items.push(Resource {
            name: name.to_string(),
            aliases,
            kind: ResourceType::Mime(MimeType::from_extension(name)),
            content: content.to_string(),
            dependencies: vec![],
            permission: PermissionMask::default(),
        });
    }

    if items.is_empty() {
        return 0;
    }
    let count = items.len();
    let engine = unsafe { &mut *(engine as *mut Engine) };
    engine.use_resources(items);
    count as i32
}

/// Destroys an engine created by `paani_adblock_engine_create`.
///
/// # Safety
///
/// `engine` must be a pointer returned by `paani_adblock_engine_create` that
/// has not been destroyed yet.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn paani_adblock_engine_destroy(engine: *mut c_void) {
    if engine.is_null() {
        return;
    }
    drop(unsafe { Box::from_raw(engine as *mut Engine) });
}

/// Checks whether a request should be blocked.
///
/// Returns `PAANI_ADBLOCK_BLOCK`, `PAANI_ADBLOCK_ALLOW` or
/// `PAANI_ADBLOCK_ERROR`.  When the request is allowed but a filter rule asked
/// for the URL to be rewritten, `out_rewritten_url` receives a newly allocated
/// NUL terminated string that the caller has to release with
/// `paani_adblock_free_string`.
///
/// # Safety
///
/// `engine` must be a pointer returned by `paani_adblock_engine_create` that
/// is only used from the calling thread.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn paani_adblock_check(
    engine: *mut c_void,
    url: *const u8,
    url_len: usize,
    source_url: *const u8,
    source_url_len: usize,
    request_type: *const u8,
    request_type_len: usize,
    method: *const u8,
    method_len: usize,
    out_rewritten_url: *mut *mut c_char,
    out_redirect: *mut *mut c_char,
) -> i32 {
    if !out_rewritten_url.is_null() {
        unsafe { *out_rewritten_url = std::ptr::null_mut() };
    }
    if !out_redirect.is_null() {
        unsafe { *out_redirect = std::ptr::null_mut() };
    }

    if engine.is_null() {
        return PAANI_ADBLOCK_ERROR;
    }

    let Some(url) = (unsafe { str_from_raw(url, url_len) }) else {
        return PAANI_ADBLOCK_ERROR;
    };
    let Some(source_url) = (unsafe { str_from_raw(source_url, source_url_len) }) else {
        return PAANI_ADBLOCK_ERROR;
    };
    let Some(request_type) = (unsafe { str_from_raw(request_type, request_type_len) }) else {
        return PAANI_ADBLOCK_ERROR;
    };
    let method = unsafe { str_from_raw(method, method_len) }.unwrap_or("get");

    let Ok(request) = Request::new(url, source_url, request_type, method) else {
        // A URL without a usable hostname cannot match any rule.
        return PAANI_ADBLOCK_ALLOW;
    };

    let engine = unsafe { &*(engine as *const Engine) };
    let result = engine.check_network_request(&request);
    let should_block = result.should_block();

    if let Some(rewritten) = result.rewritten_url {
        if !out_rewritten_url.is_null() {
            let owned = CString::new(rewritten).unwrap_or_default();
            unsafe { *out_rewritten_url = owned.into_raw() };
        }
    }

    // The engine only reports a redirect once a stub with that name is
    // loaded, so None here can mean either no match or an unknown resource.
    if let Some(redirect) = result.redirect {
        if !out_redirect.is_null() {
            let owned = CString::new(redirect).unwrap_or_default();
            unsafe { *out_redirect = owned.into_raw() };
        }
    }

    if should_block {
        PAANI_ADBLOCK_BLOCK
    } else {
        PAANI_ADBLOCK_ALLOW
    }
}

/// Releases a string returned by `paani_adblock_check`.
///
/// # Safety
///
/// `value` must be a pointer returned by `paani_adblock_check` that has not
/// been released yet.
#[unsafe(no_mangle)]
pub unsafe extern "C" fn paani_adblock_free_string(value: *mut c_char) {
    if value.is_null() {
        return;
    }
    drop(unsafe { CString::from_raw(value) });
}
