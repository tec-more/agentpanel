/**
 * 连线渲染工具 - 支持多种连线类型
 */

// 从全局配置中获取默认连线类型
export const getDefaultEdgeType = () => {
  return typeof __DEFAULT_EDGE_TYPE__ !== 'undefined' ? __DEFAULT_EDGE_TYPE__ : 'step';
};

// 1. 直线连线
export const getStraightEdgePath = (sourceX, sourceY, targetX, targetY) => {
  return `M ${sourceX} ${sourceY} L ${targetX} ${targetY}`;
};

// 2. 阶梯线连线
export const getStepEdgePath = (sourceX, sourceY, targetX, targetY, offset = 0) => {
  const mx = (sourceX + targetX) / 2;
  const sy = sourceY + offset;
  const ty = targetY + offset;
  return `M ${sourceX} ${sy} L ${mx} ${sy} L ${mx} ${ty} L ${targetX} ${ty}`;
};

// 3. 贝塞尔曲线连线
export const getBezierEdgePath = (sourceX, sourceY, targetX, targetY, offset = 0) => {
  const dx = targetX - sourceX;
  const curvature = Math.min(Math.abs(dx) * 0.3, 100);
  
  const cp1x = sourceX + curvature;
  const cp1y = sourceY + offset;
  const cp2x = targetX - curvature;
  const cp2y = targetY + offset;
  
  return `M ${sourceX} ${sourceY} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${targetX} ${targetY}`;
};

// 4. 平滑贝塞尔曲线连线
export const getSmoothBezierEdgePath = (sourceX, sourceY, targetX, targetY, offset = 0) => {
  const dx = targetX - sourceX;
  const dy = targetY - sourceY;
  
  let controlFactor = Math.min(Math.abs(dx) * 0.5, 150);
  
  let cp1x, cp1y, cp2x, cp2y;
  
  if (dx > 0) {
    cp1x = sourceX + controlFactor;
    cp1y = sourceY + offset;
    cp2x = targetX - controlFactor;
    cp2y = targetY + offset;
  } else if (dx <= 0 && dy !== 0) {
    const largeFactor = Math.min(Math.abs(dx) * 0.6, 200);
    if (dy > 0) {
      cp1x = sourceX + largeFactor;
      cp1y = sourceY + largeFactor * 0.3;
      cp2x = targetX - largeFactor;
      cp2y = targetY + largeFactor * 0.3;
    } else {
      cp1x = sourceX + largeFactor;
      cp1y = sourceY - largeFactor * 0.3;
      cp2x = targetX - largeFactor;
      cp2y = targetY - largeFactor * 0.3;
    }
  } else {
    cp1x = sourceX + 80;
    cp1y = sourceY + (dy > 0 ? 40 : -40);
    cp2x = targetX - 80;
    cp2y = targetY + (dy > 0 ? -40 : 40);
  }
  
  return `M ${sourceX} ${sourceY} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${targetX} ${targetY}`;
};

// 5. 平滑阶梯连线
export const getSmoothStepEdgePath = (sourceX, sourceY, targetX, targetY, offset = 0) => {
  const dx = targetX - sourceX;
  const dy = targetY - sourceY;
  
  const curvatureFactor = Math.min(Math.max(Math.abs(dx) * 0.5, 50), 200);
  
  let cp1x, cp1y, cp2x, cp2y;
  
  if (dx >= 0) {
    cp1x = sourceX + curvatureFactor;
    cp1y = sourceY + offset;
    cp2x = targetX - curvatureFactor;
    cp2y = targetY + offset;
  } else {
    const largeCurvature = Math.min(Math.abs(dx) * 0.7, 250);
    
    if (dy > 0) {
      cp1x = sourceX + largeCurvature;
      cp1y = sourceY + largeCurvature * 0.4;
      cp2x = targetX - largeCurvature;
      cp2y = targetY + largeCurvature * 0.4;
    } else if (dy < 0) {
      cp1x = sourceX + largeCurvature;
      cp1y = sourceY - largeCurvature * 0.4;
      cp2x = targetX - largeCurvature;
      cp2y = targetY - largeCurvature * 0.4;
    } else {
      cp1x = sourceX + largeCurvature;
      cp1y = sourceY;
      cp2x = targetX - largeCurvature;
      cp2y = targetY;
    }
  }
  
  return `M ${sourceX} ${sourceY} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${targetX} ${targetY}`;
};

// 根据类型获取连线路径
export const getEdgePathByType = (type, sourceX, sourceY, targetX, targetY, offset = 0) => {
  switch (type) {
    case 'straight':
      return getStraightEdgePath(sourceX, sourceY, targetX, targetY);
    case 'step':
      return getStepEdgePath(sourceX, sourceY, targetX, targetY, offset);
    case 'bezier':
      return getBezierEdgePath(sourceX, sourceY, targetX, targetY, offset);
    case 'smoothbezier':
      return getSmoothBezierEdgePath(sourceX, sourceY, targetX, targetY, offset);
    case 'smoothstep':
    default:
      return getSmoothStepEdgePath(sourceX, sourceY, targetX, targetY, offset);
  }
};
