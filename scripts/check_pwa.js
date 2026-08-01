const fs = require('fs');
const path = require('path');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'app.html'), 'utf8');
for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) {
  new Function(match[1]);
}

const manifest = JSON.parse(
  fs.readFileSync(path.join(root, 'static', 'manifest.webmanifest'), 'utf8')
);
for (const icon of manifest.icons || []) {
  const relative = icon.src.replace(/^\.\//, '').replace(/^static\//, 'static/');
  const iconPath = path.join(root, relative);
  if (!fs.existsSync(iconPath)) throw new Error(`Missing PWA icon: ${icon.src}`);
}

console.log('PWA manifest, icons and inline scripts: ok');
