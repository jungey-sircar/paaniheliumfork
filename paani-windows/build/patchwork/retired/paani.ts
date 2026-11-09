// Copyright 2026 The Paani Browser Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

import {CrLitElement, html} from '//resources/lit/v3_0/lit.rollup.js';

import {getCss} from './paani.css.js';
import {browserProxyFactory} from './paani.mojom-webui.js';
import type {BrowserProxy} from './paani.mojom-webui.js';

export class PaaniAppElement extends CrLitElement {
  static get is() {
    return 'paani-app';
  }

  static override get styles() {
    return getCss();
  }

  static override get properties() {
    return {
      enabled_: {type: Boolean},
      blockedCount_: {type: Number},
      allowedSites_: {type: Array},
      siteInput_: {type: String},
    };
  }

  protected accessor enabled_ = true;
  protected accessor blockedCount_ = 0;
  protected accessor allowedSites_: string[] = [];
  protected accessor siteInput_ = '';

  private browserProxy_: BrowserProxy = browserProxyFactory.getInstance();

  override connectedCallback() {
    super.connectedCallback();
    this.refresh_();
  }

  override render() {
    return html`
      <div class="page">
        <div class="brand">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path fill="var(--paani-accent)"
                  d="M12 2.2c-.3 0-.6.2-.7.5C10 6.4 6.5 9.6 6.5 14a5.5 5.5 0 0 0 11 0c0-4.4-3.5-7.6-4.8-11.3-.1-.3-.4-.5-.7-.5Z"></path>
            <path fill="var(--paani-accent-soft)"
                  d="M9.4 13.8c0 2 1.1 3.4 2.6 3.9.3.1.5-.2.3-.5-1-1.3-1.4-2.6-1.2-4 .1-.9-.8-1-.9-.5-.3.3-.5.6-.5 1.1Z"></path>
          </svg>
          <div>
            <h1>Paani</h1>
            <div class="subtitle">Privacy and ad blocking</div>
          </div>
        </div>

        <div class="card">
          <div class="row">
            <div>
              <div class="label">Ad blocking</div>
              <div class="hint">
                Blocks network requests that the filter lists match.
              </div>
            </div>
            <button
              class="toggle"
              role="switch"
              aria-checked="${this.enabled_ ? 'true' : 'false'}"
              @click="${this.onToggleClick_}"></button>
          </div>
        </div>

        <div class="card">
          <div class="row">
            <div>
              <div class="counter">${this.blockedCount_}</div>
              <div class="hint">requests blocked since the counter was reset</div>
            </div>
            <button
              class="secondary"
              @click="${this.onResetClick_}">Reset counter</button>
          </div>
        </div>

        <div class="card">
          <div class="label">Allowed sites</div>
          <div class="hint">
            Requests to these sites are never blocked.
          </div>
          <div class="row" style="margin-top:12px">
            <input
              type="text"
              placeholder="example.com"
              .value="${this.siteInput_}"
              @input="${this.onSiteInput_}"
              @keydown="${this.onSiteKeyDown_}" />
            <button @click="${this.onAddClick_}">Add</button>
          </div>
          ${this.allowedSites_.length === 0 ? html`
            <div class="empty">No sites are allowed yet.</div>` : html`
            <ul>
              ${this.allowedSites_.map((site) => html`
                <li>
                  <span>${site}</span>
                  <button
                    class="secondary"
                    @click="${() => this.onRemoveClick_(site)}">Remove</button>
                </li>`)}
            </ul>`}
        </div>

        <div class="footnote">
          Paani stops requests that the built in filter lists match. It does not
          hide page elements, so an ad slot can still take up space, and no
          blocker catches every ad.
        </div>
      </div>`;
  }

  private async refresh_(): Promise<void> {
    try {
      const state = await this.browserProxy_.handler.getState();
      this.enabled_ = state.enabled;
      this.blockedCount_ = Number(state.blockedCount);
      this.allowedSites_ = state.allowedSites;
    } catch (e) {
      console.warn('Failed to read the Paani ad blocker state', e);
    }
  }

  private onToggleClick_ = async () => {
    try {
      const response = await this.browserProxy_.handler.setEnabled(!this.enabled_);
      this.enabled_ = response.enabled;
    } catch (e) {
      console.warn('Failed to change the ad blocker state', e);
    }
  };

  private onResetClick_ = async () => {
    try {
      const response = await this.browserProxy_.handler.resetCounter();
      this.blockedCount_ = Number(response.blockedCount);
    } catch (e) {
      console.warn('Failed to reset the counter', e);
    }
  };

  private onSiteInput_ = (event: Event) => {
    this.siteInput_ = (event.target as HTMLInputElement).value;
  };

  private onSiteKeyDown_ = (event: KeyboardEvent) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      this.onAddClick_();
    }
  };

  private onAddClick_ = async () => {
    const site = this.siteInput_.trim().toLowerCase();
    if (!site) {
      return;
    }
    try {
      const response = await this.browserProxy_.handler.allowSite(site);
      this.allowedSites_ = response.allowedSites;
      this.siteInput_ = '';
    } catch (e) {
      console.warn('Failed to allow the site', e);
    }
  };

  private onRemoveClick_ = async (site: string) => {
    try {
      const response = await this.browserProxy_.handler.disallowSite(site);
      this.allowedSites_ = response.allowedSites;
    } catch (e) {
      console.warn('Failed to disallow the site', e);
    }
  };
}

declare global {
  interface HTMLElementTagNameMap {
    'paani-app': PaaniAppElement;
  }
}

customElements.define(PaaniAppElement.is, PaaniAppElement);
