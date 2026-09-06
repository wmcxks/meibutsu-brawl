import { defineConfig, loadEnv } from 'vite'
import tailwindcss from '@tailwindcss/vite'

// 读取环境变量（公共 import.meta.env 需要 VITE_ 前缀；这里的 base 由 VITE_CDN_BASE 控制）
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // H3：资源走 CDN/OSS 时构建期注入（如 https://cdn.example.com/meibutsu-h5/）
  const base = env.VITE_CDN_BASE || '/'
  return {
    plugins: [tailwindcss()],
    base,
    server: {
      // 监听所有网卡，允许局域网其他设备（手机/平板）通过本机 IP 访问
      host: true,
    },
    preview: {
      host: true,
    },
  }
})
