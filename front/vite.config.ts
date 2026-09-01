import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
  server: {
    // 监听所有网卡，允许局域网其他设备（手机/平板）通过本机 IP 访问
    host: true,
  },
  preview: {
    host: true,
  },
})
