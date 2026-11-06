import request, { createRequestWithTimeout } from '@/utils/request'

const testRequest = createRequestWithTimeout(120000)
const executeRequest = createRequestWithTimeout(600000)

export function envCheck() {
  return request.get('/v1/install/env-check')
}

export function getInstallStatus() {
  return request.get('/v1/install/status')
}

export function testDatabaseConnection(data) {
  return testRequest.post('/v1/install/test-database', data)
}

export function executeInstallation(data) {
  return executeRequest.post('/v1/install/execute', data)
}

export function resetInstallation() {
  return request.post('/v1/install/reset')
}
