<template>
  <div class="landing-page">
    <!-- 导航栏 -->
    <header class="header">
      <div class="header-content">
        <div class="logo">
          <img src="@/assets/logo.svg" alt="Logo" />
          <h1>{{ system.productName }}</h1>
        </div>
      </div>
    </header>

    <!-- Hero区域 -->
    <section class="hero">
      <div class="hero-content">
        <h1 class="hero-title">{{ system.productName }}</h1>
        <p class="hero-subtitle">轻松分享快乐时光，让欢声笑语传递每一个人</p>
        <div class="hero-buttons">
          <el-button type="primary" size="large" @click="scrollToDownload">
            <el-icon><Download /></el-icon>
            立即下载
          </el-button>
          <el-button size="large" @click="scrollToFeatures">
            了解更多
          </el-button>
        </div>
      </div>
    </section>

    <!-- 功能介绍 -->
    <section id="features" class="features">
      <div class="container">
        <h2 class="section-title">核心功能</h2>
        <p class="section-subtitle">简单有趣，快乐无限</p>

        <el-row :gutter="30" class="feature-cards">
          <el-col :xs="24" :sm="12" :md="8">
            <div class="feature-card">
              <div class="feature-icon">
                <el-icon :size="60"><ChatDotSquare /></el-icon>
              </div>
              <h3>实时互动</h3>
              <p>支持多人实时语音对话，笑声不断，快乐不停</p>
            </div>
          </el-col>

          <el-col :xs="24" :sm="12" :md="8">
            <div class="feature-card">
              <div class="feature-icon">
                <el-icon :size="60"><Microphone /></el-icon>
              </div>
              <h3>语音识别</h3>
              <p>智能语音识别技术，自动转文字，记录精彩瞬间</p>
            </div>
          </el-col>

          <el-col :xs="24" :sm="12" :md="8">
            <div class="feature-card">
              <div class="feature-icon">
                <el-icon :size="60"><Star /></el-icon>
              </div>
              <h3>积分奖励</h3>
              <p>完善的游戏化积分系统，让您越玩越开心</p>
            </div>
          </el-col>
        </el-row>
      </div>
    </section>

    <!-- 应用截图 -->
    <section class="screenshots">
      <div class="container">
        <h2 class="section-title">应用截图</h2>
        <el-row :gutter="20">
          <el-col :xs="24" :md="12">
            <div class="screenshot-placeholder">
              <el-icon :size="200"><Monitor /></el-icon>
              <p>PC端界面</p>
            </div>
          </el-col>
          <el-col :xs="24" :md="12">
            <div class="screenshot-placeholder">
              <el-icon :size="200"><Iphone /></el-icon>
              <p>移动端界面</p>
            </div>
          </el-col>
        </el-row>
      </div>
    </section>

    <!-- 下载区域 -->
    <section id="download" class="download">
      <div class="container">
        <h2 class="section-title">立即下载</h2>
        <p class="section-subtitle">选择适合您的平台，开启快乐之旅</p>

        <div class="download-options">
          <!-- Windows -->
          <div class="download-card">
            <div class="platform-icon">
              <el-icon :size="80"><Monitor /></el-icon>
            </div>
            <h3>Windows 版</h3>
            <p>支持 Windows 10/11</p>
            <el-button type="primary" size="large" @click="downloadWindows">
              <el-icon><Download /></el-icon>
              下载 Windows 版
            </el-button>
            <p class="version-info">版本：v1.0.0 | 大小：50MB</p>
          </div>

          <!-- Android -->
          <div class="download-card">
            <div class="platform-icon">
              <el-icon :size="80"><Cellphone /></el-icon>
            </div>
            <h3>Android 版</h3>
            <p>支持 Android 7.0+</p>
            <el-button type="success" size="large" @click="downloadAndroid">
              <el-icon><Download /></el-icon>
              下载 Android 版
            </el-button>
            <p class="version-info">版本：v1.0.0 | 大小：30MB</p>
          </div>

          <!-- iOS -->
          <div class="download-card coming-soon">
            <div class="platform-icon">
              <el-icon :size="80"><Iphone /></el-icon>
            </div>
            <h3>iOS 版</h3>
            <p>敬请期待...</p>
            <el-button size="large" disabled>
              即将上线
            </el-button>
            <p class="version-info">开发中</p>
          </div>
        </div>
      </div>
    </section>

    <!-- 页脚 -->
    <footer class="footer">
      <div class="container">
        <p>&copy; {{ currentYear }} {{ system.productName }}. All rights reserved.</p>
        <p>联系我们：sales@aif2f.cloud</p>
      </div>
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import {
  Download,
  ChatDotSquare,
  Microphone,
  Star,
  Monitor,
  Cellphone,
  Iphone
} from '@element-plus/icons-vue'
import { useSystemStore } from '@/stores/system'

const system = useSystemStore()

// 获取当前年份
const currentYear = ref(new Date().getFullYear())

const scrollToFeatures = () => {
  document.getElementById('features').scrollIntoView({ behavior: 'smooth' })
}

const scrollToDownload = () => {
  document.getElementById('download').scrollIntoView({ behavior: 'smooth' })
}

const downloadWindows = () => {
  // TODO: 实现Windows下载逻辑
  console.log('下载Windows版')
  window.open('/files/joke-face-to-face-windows-v1.0.0.exe', '_blank')
}

const downloadAndroid = () => {
  // TODO: 实现Android下载逻辑
  console.log('下载Android版')
  window.open('/files/joke-face-to-face-android-v1.0.0.apk', '_blank')
}
</script>

<style lang="scss" scoped>
.landing-page {
  min-height: 100vh;
  background: #f5f7fa;
}

/* 导航栏 */
.header {
  background: #fff;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  position: sticky;
  top: 0;
  z-index: 100;

  .header-content {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 20px;
    height: 64px;
    display: flex;
    align-items: center;
  }

  .logo {
    display: flex;
    align-items: center;
    gap: 12px;

    img {
      width: 40px;
      height: 40px;
    }

    h1 {
      font-size: 20px;
      color: #333;
      margin: 0;
    }
  }
}

/* Hero区域 */
.hero {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  padding: 120px 20px;
  text-align: center;

  .hero-content {
    max-width: 800px;
    margin: 0 auto;
  }

  .hero-title {
    font-size: 56px;
    font-weight: bold;
    margin-bottom: 20px;
  }

  .hero-subtitle {
    font-size: 24px;
    margin-bottom: 40px;
    opacity: 0.9;
  }

  .hero-buttons {
    display: flex;
    gap: 16px;
    justify-content: center;
  }
}

/* 通用section样式 */
section {
  padding: 80px 20px;

  &.features {
    background: #fff;
  }

  &.screenshots {
    background: #f5f7fa;
  }

  &.download {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: #fff;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
  }
}

.section-title {
  font-size: 40px;
  text-align: center;
  margin-bottom: 16px;
}

.section-subtitle {
  font-size: 18px;
  text-align: center;
  color: #666;
  margin-bottom: 60px;

  .download & {
    color: rgba(255, 255, 255, 0.9);
  }
}

/* 功能卡片 */
.feature-cards {
  margin-top: 40px;
}

.feature-card {
  text-align: center;
  padding: 40px 20px;
  background: #f9f9f9;
  border-radius: 12px;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-8px);
    box-shadow: 0 12px 24px rgba(0, 0, 0, 0.1);
  }

  .feature-icon {
    color: #667eea;
    margin-bottom: 20px;
  }

  h3 {
    font-size: 24px;
    margin-bottom: 12px;
  }

  p {
    color: #666;
    font-size: 16px;
  }
}

/* 截图占位 */
.screenshot-placeholder {
  text-align: center;
  padding: 60px;
  background: #fff;
  border-radius: 12px;

  .el-icon {
    color: #ddd;
  }

  p {
    margin-top: 20px;
    font-size: 18px;
    color: #666;
  }
}

/* 下载卡片 */
.download-options {
  display: flex;
  gap: 30px;
  justify-content: center;
  flex-wrap: wrap;
}

.download-card {
  background: #fff;
  border-radius: 16px;
  padding: 40px;
  text-align: center;
  min-width: 280px;
  color: #333;
  transition: all 0.3s;

  &:hover {
    transform: translateY(-8px);
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.15);
  }

  &.coming-soon {
    opacity: 0.7;
  }

  .platform-icon {
    color: #667eea;
    margin-bottom: 20px;
  }

  h3 {
    font-size: 28px;
    margin-bottom: 8px;
  }

  p {
    color: #666;
    margin-bottom: 20px;
  }

  .version-info {
    font-size: 14px;
    color: #999;
    margin-top: 16px;
  }
}

/* 页脚 */
.footer {
  background: #333;
  color: #fff;
  padding: 40px 20px;
  text-align: center;

  p {
    margin: 8px 0;
    color: rgba(255, 255, 255, 0.7);
  }
}

/* 响应式 */
@media (max-width: 768px) {
  .hero-title {
    font-size: 36px;
  }

  .hero-subtitle {
    font-size: 18px;
  }

  .section-title {
    font-size: 32px;
  }

  .download-options {
    flex-direction: column;
    align-items: center;
  }
}
</style>


