# 应用下载文件

将应用安装包放在此目录，供用户下载。

## 文件命名规范

- Windows 版：`joke-face-to-face-windows-v{版本号}.exe`
- Android 版：`joke-face-to-face-android-v{版本号}.apk`
- iOS 版：暂不支持

## 更新下载链接

在 `web/src/views/LandingPage.vue` 中更新下载方法：

```javascript
const downloadWindows = () => {
  window.open('/files/joke-face-to-face-windows-v1.0.0.exe', '_blank')
}

const downloadAndroid = () => {
  window.open('/files/joke-face-to-face-android-v1.0.0.apk', '_blank')
}
```
