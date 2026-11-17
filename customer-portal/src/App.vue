<template>
  <router-view />
</template>

<style>
:root {
  --cp-primary: #1a6d4a;
  --cp-bg: #f4f6f5;
}
* { box-sizing: border-box; }
html, body, #app { margin: 0; padding: 0; height: 100%; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--cp-bg);
  color: #1f2937;
}
</style>
