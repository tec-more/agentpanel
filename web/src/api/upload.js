import request from '@/utils/request'

// 上传图片
export function uploadImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request.post('/v1/upload/image', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}
