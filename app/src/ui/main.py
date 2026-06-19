import customtkinter as ctk
import requests
import json
import threading
import time
import os
import sys

API_BASE = 'http://127.0.0.1:3456/api'
REFRESH_INTERVAL = 5000

ctk.set_appearance_mode('dark')
ctk.set_default_color_theme('green')

class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Claim City 2026 Dashboard')
        self.geometry('900x600')
        self.minsize(700, 500)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.status_tab = self.tabview.add('Status')
        self.license_tab = self.tabview.add('License')
        self.casinos_tab = self.tabview.add('Casinos')
        self.cookies_tab = self.tabview.add('Cookies')
        self.claims_tab = self.tabview.add('Claims')

        self._build_status_tab()
        self._build_license_tab()
        self._build_casinos_tab()
        self._build_cookies_tab()
        self._build_claims_tab()

        self.after(100, self._refresh_all)

    def _api(self, method, path, data=None):
        try:
            url = f'{API_BASE}{path}'
            r = requests.request(method, url, json=data, timeout=5)
            return r.json() if r.status_code < 300 else None
        except:
            return None

    def _build_status_tab(self):
        self.status_tab.grid_columnconfigure(0, weight=1)
        self.status_tab.grid_rowconfigure(2, weight=1)

        self.status_text = ctk.CTkTextbox(self.status_tab, height=200, wrap='word', font=('Consolas', 13))
        self.status_text.grid(row=0, column=0, padx=10, pady=(10, 5), sticky='ew')
        self.status_text.insert('1.0', 'Connecting to bot...')
        self.status_text.configure(state='disabled')

        self.scan_btn = ctk.CTkButton(self.status_tab, text='Scan for Dailies', command=self._scan_dailies)
        self.scan_btn.grid(row=1, column=0, padx=10, pady=5, sticky='ew')

        self.claim_btn = ctk.CTkButton(self.status_tab, text='Claim Available Daily SC', fg_color='#2d8a4e', hover_color='#236b3d', command=self._claim_dailies)
        self.claim_btn.grid(row=2, column=0, padx=10, pady=5, sticky='n')

    def _build_license_tab(self):
        self.license_tab.grid_columnconfigure(0, weight=1)
        self.license_tab.grid_columnconfigure(1, weight=2)

        ctk.CTkLabel(self.license_tab, text='Current License Key:').grid(row=0, column=0, padx=10, pady=(20, 5), sticky='e')
        self.license_entry = ctk.CTkEntry(self.license_tab, width=350)
        self.license_entry.grid(row=0, column=1, padx=10, pady=(20, 5), sticky='w')

        ctk.CTkLabel(self.license_tab, text='Status:').grid(row=1, column=0, padx=10, pady=5, sticky='e')
        self.license_status = ctk.CTkLabel(self.license_tab, text='Unknown', text_color='#aaaaaa')
        self.license_status.grid(row=1, column=1, padx=10, pady=5, sticky='w')

        self.save_license_btn = ctk.CTkButton(self.license_tab, text='Save License Key', command=self._save_license)
        self.save_license_btn.grid(row=2, column=1, padx=10, pady=10, sticky='w')

    def _build_casinos_tab(self):
        self.casinos_tab.grid_columnconfigure(0, weight=1)
        self.casinos_tab.grid_rowconfigure(0, weight=1)

        self.casinos_frame = ctk.CTkScrollableFrame(self.casinos_tab)
        self.casinos_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

    def _build_cookies_tab(self):
        self.cookies_tab.grid_columnconfigure(0, weight=1)
        self.cookies_tab.grid_rowconfigure(0, weight=1)
        self.cookies_tab.grid_rowconfigure(1, weight=0)

        self.cookies_frame = ctk.CTkScrollableFrame(self.cookies_tab)
        self.cookies_frame.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')

        self.paste_cookie_btn = ctk.CTkButton(self.cookies_tab, text='Paste Cookie from Clipboard', command=self._paste_cookie)
        self.paste_cookie_btn.grid(row=1, column=0, padx=10, pady=5, sticky='ew')

    def _build_claims_tab(self):
        self.claims_tab.grid_columnconfigure(0, weight=1)
        self.claims_tab.grid_rowconfigure(0, weight=1)
        self.claims_tab.grid_rowconfigure(1, weight=0)

        self.claims_text = ctk.CTkTextbox(self.claims_tab, wrap='word', font=('Consolas', 12))
        self.claims_text.grid(row=0, column=0, padx=10, pady=10, sticky='nsew')
        self.claims_text.insert('1.0', 'Loading claim history...')
        self.claims_text.configure(state='disabled')

        self.refresh_claims_btn = ctk.CTkButton(self.claims_tab, text='Refresh History', command=self._refresh_claims)
        self.refresh_claims_btn.grid(row=1, column=0, padx=10, pady=5, sticky='ew')

    def _refresh_all(self):
        self._refresh_status()
        self._refresh_license()
        self._refresh_casinos()
        self._refresh_cookies()
        self._refresh_claims()
        self.after(REFRESH_INTERVAL, self._refresh_all)

    def _refresh_status(self):
        s = self._api('GET', '/status')
        if not s:
            self._set_status_text('Cannot connect to bot. Make sure CasinoBot.exe is running.')
            return
        lines = [
            f'Bot Status:     {"ONLINE" if s.get("online") else "OFFLINE"}',
            f'Ping:           {s.get("ping", 0)} ms',
            f'Uptime:         {int(s.get("uptime", 0) // 60)}m {int(s.get("uptime", 0) % 60)}s',
            f'Guilds:         {s.get("guilds", 0)}',
            f'Monitor Ch:     {"Connected" if s.get("monitorChannel") else "Not set"}',
            f'Streamer Ch:    {"Connected" if s.get("streamerChannel") else "Not set"}',
            f'Daily Claims Ch: {"Connected" if s.get("dailyClaimsChannel") else "Not set"}',
        ]
        self._set_status_text('\n'.join(lines))

    def _set_status_text(self, text):
        self.status_text.configure(state='normal')
        self.status_text.delete('1.0', 'end')
        self.status_text.insert('1.0', text)
        self.status_text.configure(state='disabled')

    def _refresh_license(self):
        l = self._api('GET', '/license')
        if not l:
            self.license_entry.delete(0, 'end')
            self.license_entry.insert(0, '')
            self.license_status.configure(text='Cannot reach bot', text_color='#ff4444')
            return
        key = l.get('key') or ''
        self.license_entry.delete(0, 'end')
        self.license_entry.insert(0, key)
        if l.get('valid'):
            self.license_status.configure(text='VALID', text_color='#57F287')
        elif key:
            self.license_status.configure(text='INVALID', text_color='#ff4444')
        else:
            self.license_status.configure(text='Not set', text_color='#aaaaaa')

    def _save_license(self):
        key = self.license_entry.get().strip()
        if not key:
            return
        r = self._api('PUT', '/license', {'key': key})
        if r and r.get('success'):
            self.license_status.configure(text='Saved & Valid', text_color='#57F287')
        else:
            self.license_status.configure(text='Invalid Key', text_color='#ff4444')

    def _refresh_casinos(self):
        for w in self.casinos_frame.winfo_children():
            w.destroy()
        casinos = self._api('GET', '/casinos')
        if not casinos:
            ctk.CTkLabel(self.casinos_frame, text='Cannot load casinos').pack(pady=10)
            return
        for c in casinos:
            row = ctk.CTkFrame(self.casinos_frame)
            row.pack(fill='x', padx=5, pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=c['name'], font=('Segoe UI', 13, 'bold')).grid(row=0, column=0, padx=10, pady=5, sticky='w')
            var = ctk.BooleanVar(value=c['enabled'])
            def toggle(n=c['name'], v=var):
                self._api('PUT', f'/casinos/{n}', {'enabled': v.get()})
            ctk.CTkSwitch(row, text='Enabled' if c['enabled'] else 'Disabled', variable=var, command=toggle, onvalue=True, offvalue=False).grid(row=0, column=1, padx=10, pady=5)

    def _refresh_cookies(self):
        for w in self.cookies_frame.winfo_children():
            w.destroy()
        cookies = self._api('GET', '/cookies')
        if not cookies:
            ctk.CTkLabel(self.cookies_frame, text='Cannot load cookies').pack(pady=10)
            return
        if len(cookies) == 0:
            ctk.CTkLabel(self.cookies_frame, text='No cookies saved yet. Use /setcookie in Discord or paste one below.').pack(pady=10)
            return
        for c in cookies:
            row = ctk.CTkFrame(self.cookies_frame)
            row.pack(fill='x', padx=5, pady=2)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=c['casino'], font=('Segoe UI', 13)).grid(row=0, column=0, padx=10, pady=5, sticky='w')
            def delete(n=c['casino']):
                self._api('DELETE', f'/cookies/{n}')
                self._refresh_cookies()
            ctk.CTkButton(row, text='Delete', fg_color='#c0392b', hover_color='#96281b', width=80, command=delete).grid(row=0, column=1, padx=10, pady=5)

    def _paste_cookie(self):
        dialog = ctk.CTkInputDialog(text='Casino name:', title='Save Cookie')
        casino = dialog.get_input()
        if not casino:
            return
        cookie = self.clipboard_get() if self.clipboard_get() else ''
        if not cookie:
            return
        self._api('PUT', f'/cookies/{casino}', {'cookie': cookie})
        self._refresh_cookies()

    def _refresh_claims(self):
        history = self._api('GET', '/claims/history')
        self.claims_text.configure(state='normal')
        self.claims_text.delete('1.0', 'end')
        if not history or len(history) == 0:
            self.claims_text.insert('1.0', 'No claim history yet.')
        else:
            lines = []
            for h in history:
                icon = '✅' if h.get('success') else '❌'
                casino = h.get('casino', 'Unknown')
                date = h.get('date', '')
                status = h.get('status') or h.get('error') or 'ok'
                lines.append(f'{icon} {casino} — {status}  ({date})')
            self.claims_text.insert('1.0', '\n'.join(lines))
        self.claims_text.configure(state='disabled')

    def _scan_dailies(self):
        self.scan_btn.configure(state='disabled', text='Scanning...')
        def work():
            r = self._api('POST', '/claims/scan')
            self.after(0, lambda: self._scan_done(r))
        threading.Thread(target=work, daemon=True).start()

    def _scan_done(self, result):
        self.scan_btn.configure(state='normal', text='Scan for Dailies')
        if not result:
            return
        results = result.get('results', [])
        lines = []
        for r in results:
            if r.get('error'):
                lines.append(f'❌ {r["casino"]} — {r["error"]}')
            elif r.get('available'):
                lines.append(f'✅ {r["casino"]} — Bonus available!')
            elif r.get('alreadyClaimed'):
                lines.append(f'⏳ {r["casino"]} — Already claimed today')
            else:
                lines.append(f'❓ {r["casino"]} — No bonus detected')
        self._set_status_text('\n'.join(lines) if lines else 'No casinos scanned.')

    def _claim_dailies(self):
        self.claim_btn.configure(state='disabled', text='Claiming...')
        def work():
            r = self._api('POST', '/claims/claim')
            self.after(0, lambda: self._claim_done(r))
        threading.Thread(target=work, daemon=True).start()

    def _claim_done(self, result):
        self.claim_btn.configure(state='normal', text='Claim Available Daily SC')
        if not result:
            return
        results = result.get('results', [])
        lines = []
        for r in results:
            lines.append(f'{"✅" if r.get("success") else "❌"} {r["casino"]} — {r.get("status") or r.get("error") or "ok"}')
        self._set_status_text('\n'.join(lines) if lines else 'No claims attempted.')

if __name__ == '__main__':
    app = DashboardApp()
    app.mainloop()
