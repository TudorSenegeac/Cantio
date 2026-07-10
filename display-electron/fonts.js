/**
 * Cantio — shared font catalog (100 families).
 * Loaded by both the editors and the live display so a font chosen in the
 * editor renders identically on the projector.
 *
 * Fonts load from Google Fonts (one combined stylesheet). If the machine is
 * offline they fall back to the nearest installed family — text still shows.
 * For full offline use, drop the WOFF2 files into display-electron/fonts/ and
 * @font-face them (the family names below already match Google's).
 */
(function (global) {
  'use strict';

  const FONTS = [
    'Montserrat','Poppins','Oswald','Bebas Neue','Anton','Raleway','Roboto',
    'Open Sans','Lato','Roboto Condensed','Roboto Slab','Playfair Display',
    'Merriweather','Lora','PT Sans','PT Serif','Nunito','Nunito Sans','Quicksand',
    'Josefin Sans','Inter','Work Sans','Rubik','Mukta','Karla','Barlow',
    'Barlow Condensed','Cabin','Dosis','Comfortaa','Pacifico','Lobster',
    'Dancing Script','Great Vibes','Sacramento','Satisfy','Caveat','Kaushan Script',
    'Cookie','Allura','Parisienne','Yellowtail','Courgette','Permanent Marker',
    'Shadows Into Light','Indie Flower','Amatic SC','Architects Daughter',
    'Patrick Hand','Gloria Hallelujah','Covered By Your Grace','Rock Salt',
    'Bangers','Fredoka','Righteous','Russo One','Archivo Black','Alfa Slab One',
    'Titan One','Bungee','Black Ops One','Press Start 2P','Monoton','Audiowide',
    'Orbitron','Exo 2','Teko','Fjalla One','Abril Fatface','Cinzel','Cormorant Garamond',
    'EB Garamond','Crimson Text','Libre Baskerville','Spectral','Bitter','Arvo',
    'Bree Serif','Domine','Vollkorn','Zilla Slab','Source Sans 3','Source Serif 4',
    'Manrope','DM Sans','DM Serif Display','Sora','Outfit','Space Grotesk',
    'Jost','Lexend','Big Shoulders Display','Saira','Chakra Petch','Rajdhani',
    'Kanit','Prompt','Sarabun','Hind','Catamaran','Mulish','Heebo','Assistant',
  ];

  // Locate the bundled offline font CSS (produced by download_fonts.py). Checks
  // a few candidate dirs so it works from both display.html and the editor.
  function _localFontsCss() {
    try {
      const fs = require('fs'), path = require('path');
      const bases = [];
      try { if (typeof __dirname === 'string') bases.push(__dirname); } catch (e) {}
      try {
        const u = new URL('.', (typeof document !== 'undefined' ? document : {}).location
                  ? document.location.href : 'file:///');
        let pn = decodeURIComponent(u.pathname);
        if (/^\/[A-Za-z]:/.test(pn)) pn = pn.slice(1);   // /C:/… → C:/…
        bases.push(pn);
      } catch (e) {}
      try { bases.push(path.join(process.cwd(), 'display-electron')); } catch (e) {}
      for (const b of bases) {
        const p = path.join(b, 'fonts', 'cantio-fonts.css');
        if (fs.existsSync(p)) return true;
      }
    } catch (e) {}
    return false;
  }

  function loadGoogleFonts(doc) {
    doc = doc || document;
    if (doc.getElementById('cantio-google-fonts')) return;

    // Offline-first: use the bundled local WOFF2 font CSS when present so the
    // app needs NO internet. Falls back to Google's CDN only if not bundled.
    if (_localFontsCss()) {
      const link = doc.createElement('link');
      link.id = 'cantio-google-fonts';
      link.rel = 'stylesheet';
      link.href = 'fonts/cantio-fonts.css';   // relative to the HTML file
      (doc.head || doc.documentElement).appendChild(link);
      return;
    }

    try {
      // Build one combined Google Fonts stylesheet URL (online fallback).
      const fams = FONTS.map(f =>
        'family=' + encodeURIComponent(f).replace(/%20/g, '+') + ':wght@400;700').join('&');
      const link = doc.createElement('link');
      link.id = 'cantio-google-fonts';
      link.rel = 'stylesheet';
      link.href = 'https://fonts.googleapis.com/css2?' + fams + '&display=swap';
      (doc.head || doc.documentElement).appendChild(link);
      ['https://fonts.googleapis.com', 'https://fonts.gstatic.com'].forEach(h => {
        const pc = doc.createElement('link');
        pc.rel = 'preconnect'; pc.href = h; pc.crossOrigin = 'anonymous';
        (doc.head || doc.documentElement).appendChild(pc);
      });
    } catch (e) { /* offline → system fallback */ }
  }

  const CantioFonts = { FONTS, loadGoogleFonts };
  global.CantioFonts = CantioFonts;
  if (typeof module !== 'undefined' && module.exports) module.exports = CantioFonts;
})(typeof window !== 'undefined' ? window : globalThis);
