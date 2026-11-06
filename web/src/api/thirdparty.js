import request from '@/utils/request';

// 平台管理
export const getPlatforms = (params) => {
  return request({
    url: '/v1/thirdparty/platforms/',
    method: 'get',
    params
  });
};

export const getPlatform = (id) => {
  return request({
    url: `/v1/thirdparty/platforms/${id}/`,
    method: 'get'
  });
};

export const createPlatform = (data) => {
  return request({
    url: '/v1/thirdparty/platforms/',
    method: 'post',
    data
  });
};

export const updatePlatform = (id, data) => {
  return request({
    url: `/v1/thirdparty/platforms/${id}/`,
    method: 'put',
    data
  });
};

export const deletePlatform = (id) => {
  return request({
    url: `/v1/thirdparty/platforms/${id}/`,
    method: 'delete'
  });
};

export const testPlatformConnection = (id) => {
  return request({
    url: `/v1/thirdparty/platforms/${id}/test/`,
    method: 'post'
  });
};

// 智能体管理
export const getAgents = (params) => {
  return request({
    url: '/v1/thirdparty/agents/',
    method: 'get',
    params
  });
};

export const getAgent = (id) => {
  return request({
    url: `/v1/thirdparty/agents/${id}/`,
    method: 'get'
  });
};

export const createAgent = (data) => {
  return request({
    url: '/v1/thirdparty/agents/',
    method: 'post',
    data
  });
};

export const updateAgent = (id, data) => {
  return request({
    url: `/v1/thirdparty/agents/${id}/`,
    method: 'put',
    data
  });
};

export const deleteAgent = (id) => {
  return request({
    url: `/v1/thirdparty/agents/${id}/`,
    method: 'delete'
  });
};

export const getAgentsByPlatform = (platformId) => {
  return request({
    url: `/v1/thirdparty/agents/platform/${platformId}/`,
    method: 'get'
  });
};

export const testAgentAccess = (id) => {
  return request({
    url: `/v1/thirdparty/agents/${id}/test/`,
    method: 'post'
  });
};