// 注入全局样式，隐藏 llm-deepseek 的provider行
const style = document.createElement('style');
style.textContent = `
.provider-row[data-provider-id="llm-deepseek"] {
  display: none !important;
}
`;
document.head.appendChild(style);
