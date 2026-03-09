# My Book Tutor - Legal Pages

This folder contains the standalone legal pages for the My Book Tutor app, designed to meet Google Play Store requirements for privacy policy accessibility.

## 📄 Pages Included

- **`index.html`** - Complete legal page with:
  - Privacy Policy (Datenschutzerklärung) — incl. Privacy by Design, OpenRouter data flows, GDPR rights, ZDR settings
  - Terms of Use (Nutzungsbedingungen) — incl. AI disclaimer, product liability, copyright & private copy, intermediary liability
  - Legal Notice (Impressum) — incl. contact info, liability for content/links, copyright
  - German/English language toggle (persisted via `localStorage`)
  - Fully translated footer

## 🚀 Quick Setup for GitHub Pages

### 1. The legal page is already part of the main BuchTutor repository

The `legal/` folder is served directly via GitHub Pages from the main repo:

```
https://falkoguderian.github.io/BuchTutor/legal/
```

No separate repository is needed.

### 2. Manual deployment to a separate repo (optional)

```bash
# Clone a new public repository
git clone https://github.com/yourusername/buch-tutor-legal.git
cd buch-tutor-legal

# Copy the legal folder contents
cp -r /path/to/BuchTutor/legal/* .

# Commit and push
git add .
git commit -m "Add legal pages"
git push origin main
```

Then enable GitHub Pages under **Settings → Pages → Deploy from branch (main / root)**.

## 🌐 Google Play Store Integration

### Submit Privacy Policy URL
1. Go to Google Play Console
2. Select your app
3. Navigate to **App Content → Privacy Policy**
4. Enter the URL: `https://falkoguderian.github.io/BuchTutor/legal/`
5. Submit for review

## 🎯 Features

### ✅ Google Play Compliant
- Public URL accessible without app download
- Professional legal content presentation
- Clear language selection

### 🌍 Internationalization
- Built-in German/English support via `i18n` object in `index.html`
- Language preference persisted in `localStorage` (`legalLang` key)
- All sections fully translated: headings, paragraphs, lists, footer
- Stable ID-based DOM targeting (no fragile `nth-of-type` selectors)

### 📱 Responsive Design
- Mobile-friendly layout
- Professional appearance
- Fast loading (no build tools, CDN-only dependencies)

## 🔧 Adding New Languages

The legal pages use a JavaScript `i18n` object and a `LanguageManager` class. To add a new language:

### 1. Add language strings to the `i18n` object in `index.html`

```javascript
const i18n = {
    de: { /* existing German content */ },
    en: { /* existing English content */ },
    es: { // Spanish example
        title: "My Book Tutor - Política de Privacidad",
        header: "My Book Tutor",
        subheader: "Política de Privacidad & Información Legal",
        privacy: "📋 Política de Privacidad",
        terms: "📄 Términos de Uso",
        impressum: "🏢 Aviso Legal",
        footerCopyright: `© ${new Date().getFullYear()} My Book Tutor. Todos los derechos reservados.`,
        footerNote: "Esta política de privacidad forma parte de la infraestructura de la app.",
        // ... add all other strings
    }
};
```

### 2. Add a language button to the switcher in the HTML

```html
<div class="language-switcher">
    <button class="language-btn active" id="lang-de">🇩🇪 Deutsch</button>
    <button class="language-btn" id="lang-en">🇬🇧 English</button>
    <button class="language-btn" id="lang-es">🇪🇸 Español</button>
</div>
```

### 3. Register the button in `LanguageManager.setupEventListeners()`

```javascript
setupEventListeners() {
    document.getElementById('lang-de').addEventListener('click', () => this.switchLanguage('de'));
    document.getElementById('lang-en').addEventListener('click', () => this.switchLanguage('en'));
    document.getElementById('lang-es').addEventListener('click', () => this.switchLanguage('es'));
},
```

## 📝 Content Management

### Updating Legal Content

All legal text lives in the `i18n` object inside `index.html`. Edit the relevant key for the language you want to update — no HTML changes needed for text-only edits.

Key sections and their i18n keys:

| Section | HTML id | i18n keys |
|---|---|---|
| Privacy Policy | `#privacy` | `privacyTitle`, `privacySection1–5`, `privacyUl`, `privacyOpenRouterText`, `privacyOpenRouterList`, `privacyRightsText`, `privacySettingsText`, `privacyCheckText` |
| Terms of Use | `#terms` | `termsTitle`, `termsSection1–4`, `termsWarningText`, `termsUl`, `termsProductText`, `termsCopyrightText`, `termsIntermediaryText` |
| Legal Notice | `#impressum` | `impressumTitle`, `impressumSection1–5`, `impressumInfoHtml`, `impressumContactText`, `impressumContentText`, `impressumLinksText`, `impressumCopyrightText` |
| Footer | `footer` | `footerCopyright`, `footerNote` |
| Disclaimer box | `.highlight-box` | `disclaimerTitle`, `disclaimerText` |

### Stable DOM targeting

All dynamic elements use stable `id` attributes (e.g. `#privacy-openrouter-intro`, `#privacy-rights`, `#privacy-zdr-check`, `#impressum-info`, `#terms-copyright-list`) to avoid fragile positional selectors.

## 🛠️ Technical Details

### Dependencies
- **Tailwind CSS** (via CDN) — Styling framework
- **Lucide Icons** (via CDN, ES module) — Icon library
- **No build tools required** — Pure HTML/CSS/JavaScript

### Browser Support
- Chrome/Edge: Full support
- Firefox: Full support
- Safari: Full support
- Mobile browsers: Full responsive support

### Performance
- Fast loading (under 100 KB total)
- No external tracking scripts
- Optimized for SEO

## ⚖️ Legal Disclaimer

These legal pages are provided as a template and starting point. You should:

- Review all content for accuracy and completeness
- Consult with legal counsel for compliance
- Update content as laws and requirements change
- Ensure all information is current and accurate

The content reflects German/EU data protection requirements (DSGVO/GDPR) but may need adaptation for other jurisdictions.
