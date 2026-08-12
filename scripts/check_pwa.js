const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.resolve(__dirname, '..');
const html = fs.readFileSync(path.join(root, 'static', 'app.html'), 'utf8');
for (const match of html.matchAll(/<script>([\s\S]*?)<\/script>/g)) {
  new Function(match[1]);
}

const markdownSource = fs.readFileSync(path.join(root, 'static', 'chat-md.js'), 'utf8');
const markdownSandbox = {};
vm.runInNewContext(
  markdownSource + '\n;globalThis.__splitThinkBlocks = chMdSplitThinkBlocks;',
  markdownSandbox
);
const splitThinkBlocks = markdownSandbox.__splitThinkBlocks;
const assertParts = (name, actual, expected) => {
  const normalized = JSON.parse(JSON.stringify(actual));
  if (JSON.stringify(normalized) !== JSON.stringify(expected)) {
    throw new Error(`${name}: ${JSON.stringify(normalized)}`);
  }
};

assertParts('literary think block', splitThinkBlocks(
  '<think>\n她是不是不开心。\n</think>\n正文'
), [
  { type: 'thinking', text: '她是不是不开心。\n', complete: true },
  { type: 'text', text: '正文', complete: true },
]);
assertParts('multiple think blocks', splitThinkBlocks(
  '开头\n<think>\n一\n</think>\n中间\n<think>\n二\n</think>\n结尾'
), [
  { type: 'text', text: '开头\n', complete: true },
  { type: 'thinking', text: '一\n', complete: true },
  { type: 'text', text: '中间\n', complete: true },
  { type: 'thinking', text: '二\n', complete: true },
  { type: 'text', text: '结尾', complete: true },
]);
assertParts('streaming unfinished think block', splitThinkBlocks(
  '<think>\n还在慢慢写'
), [
  { type: 'thinking', text: '还在慢慢写', complete: false },
]);
assertParts('literal tags stay in fenced and inline code', splitThinkBlocks(
  '```xml\n<think>\n示例\n</think>\n```\n行内 `<think>` 不折叠'
), [
  {
    type: 'text',
    text: '```xml\n<think>\n示例\n</think>\n```\n行内 `<think>` 不折叠',
    complete: true,
  },
]);

if (!html.includes("sessionType === 'codex' ? '/data/home/workspace' : '~'")) {
  throw new Error('Codex sessions must default to the persistent workspace');
}

const manifest = JSON.parse(
  fs.readFileSync(path.join(root, 'static', 'manifest.webmanifest'), 'utf8')
);
for (const icon of manifest.icons || []) {
  const relative = icon.src.replace(/^\.\//, '').replace(/^static\//, 'static/');
  const iconPath = path.join(root, relative);
  if (!fs.existsSync(iconPath)) throw new Error(`Missing PWA icon: ${icon.src}`);
}

console.log('PWA manifest, think blocks, icons, inline scripts and Codex workspace default: ok');
