// Copyright 2026 The Paani Browser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {CrLitElement} from '//resources/lit/v3_0/lit.rollup.js';

import {getCss} from './app.css.js';
import {getHtml} from './app.html.js';
import {browserProxyFactory} from './paani.mojom-webui.js';
import type {BrowserProxy} from './paani.mojom-webui.js';

// The generated app.html.js types its `this` as `AppElement`, which it derives
// from this file's name, so the class has to carry that exact name.
export class AppElement extends CrLitElement {
  static get is() {
    return 'paani-app';
  }

  static override get styles() {
    return getCss();
  }

  override render() {
    return getHtml.bind(this)();
  }

  static override get properties() {
    return {
      enabled_: {type: Boolean},
      blockedCount_: {type: Number},
      allowedSites_: {type: Array},
      siteInput_: {type: String},
      engineStatus_: {type: String},
    };
  }

  protected accessor enabled_: boolean = true;
  protected accessor blockedCount_: number = 0;
  protected accessor allowedSites_: string[] = [];
  protected accessor siteInput_: string = '';
  protected accessor engineStatus_: string = 'checking the filter engine...';

  private browserProxy_: BrowserProxy = browserProxyFactory.getInstance();

  override connectedCallback() {
    super.connectedCallback();
    this.refresh_();
  }

  private async refresh_(): Promise<void> {
    try {
      const state = await this.browserProxy_.handler.getState();
      this.enabled_ = state.enabled;
      this.blockedCount_ = Number(state.blockedCount);
      this.allowedSites_ = state.allowedSites;
      const engine = state.engine;
      const pipelines = Number(engine.factoriesInstalled);
      if (!engine.engineReady) {
        this.engineStatus_ =
          `Filter engine NOT built: ${engine.listsLoaded} list(s) loaded, ` +
          `${Number(engine.approxRules)} rules read. Nothing is being blocked.`;
      } else if (pipelines === 0) {
        this.engineStatus_ =
          `Filter engine ready with ${Number(engine.approxRules).toLocaleString()} ` +
          'rules, but no page is routed through it yet.';
      } else {
        this.engineStatus_ =
          `Filter engine ready: ${engine.listsLoaded} lists, ` +
          `${Number(engine.approxRules).toLocaleString()} rules, ` +
          `${pipelines} request pipeline(s) wrapped.`;
      }
    } catch (e) {
      console.warn('Failed to read the Paani ad blocker state', e);
      this.engineStatus_ = 'Could not read the filter engine state.';
    }
  }

  protected onToggleClick_(): void {
    this.setEnabled_(!this.enabled_);
  }

  protected onResetClick_(): void {
    this.browserProxy_.handler.resetCounter().then((response) => {
      this.blockedCount_ = Number(response.blockedCount);
    });
  }

  protected onSiteInput_(event: Event): void {
    this.siteInput_ = (event.target as HTMLInputElement).value;
  }

  protected onSiteKeydown_(event: KeyboardEvent): void {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.addSite_();
    }
  }

  protected onAddClick_(): void {
    this.addSite_();
  }

  protected onRemoveClick_(event: Event): void {
    const button = event.currentTarget as HTMLElement;
    const index = Number(button.dataset['index']);
    const site = this.allowedSites_[index];
    if (!site) {
      return;
    }
    this.browserProxy_.handler.disallowSite(site).then((response) => {
      this.allowedSites_ = response.allowedSites;
    });
  }

  private addSite_(): void {
    const site = this.siteInput_.trim().toLowerCase();
    if (!site) {
      return;
    }
    this.browserProxy_.handler.allowSite(site).then((response) => {
      this.allowedSites_ = response.allowedSites;
      this.siteInput_ = '';
    });
  }

  private setEnabled_(enabled: boolean): void {
    this.browserProxy_.handler.setEnabled(enabled).then((response) => {
      this.enabled_ = response.enabled;
    });
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'paani-app': AppElement;
  }
}

customElements.define(AppElement.is, AppElement);
