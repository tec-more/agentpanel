<template>
  <div class="mes-base">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="物料管理" name="material">
        <el-card shadow="never" class="search-card">
          <el-form :inline="true" :model="materialSearch" class="search-form">
            <el-form-item label="物料编码">
              <el-input v-model="materialSearch.material_code" placeholder="请输入编码" clearable />
            </el-form-item>
            <el-form-item label="物料名称">
              <el-input v-model="materialSearch.material_name" placeholder="请输入名称" clearable />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="fetchMaterialList">搜索</el-button>
              <el-button :icon="Refresh" @click="resetMaterialSearch">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="card-header">
              <span>物料列表</span>
              <el-button type="primary" :icon="Plus" @click="handleAddMaterial">新增物料</el-button>
            </div>
          </template>
          <el-table v-loading="materialLoading" :data="materialList" border stripe>
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column prop="material_code" label="物料编码" min-width="120" />
            <el-table-column prop="material_name" label="物料名称" min-width="150" />
            <el-table-column prop="material_type" label="物料类型" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getMaterialTypeTag(row.material_type)">{{ getMaterialTypeName(row.material_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="specification" label="规格" min-width="150" />
            <el-table-column prop="drawing_code" label="图纸编号" min-width="120" />
            <el-table-column prop="unit" label="单位" width="80" align="center" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link :icon="Edit" @click="handleEditMaterial(row)">编辑</el-button>
                <el-button type="danger" link :icon="Delete" @click="handleDeleteMaterial(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="materialPagination.page"
              v-model:page-size="materialPagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="materialPagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchMaterialList"
              @current-change="fetchMaterialList"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="BOM管理" name="bom">
        <el-card shadow="never" class="search-card">
          <el-form :inline="true" :model="bomSearch" class="search-form">
            <el-form-item label="产品编码">
              <el-input v-model="bomSearch.product_code" placeholder="请输入产品编码" clearable />
            </el-form-item>
            <el-form-item label="物料编码">
              <el-input v-model="bomSearch.item_code" placeholder="请输入物料编码" clearable />
            </el-form-item>
            <el-form-item label="版本">
              <el-select v-model="bomSearch.version" placeholder="请选择版本" clearable>
                <el-option v-for="v in bomVersionOptions" :key="v.version" :label="v.version" :value="v.version" />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="fetchBomList">搜索</el-button>
              <el-button :icon="Refresh" @click="resetBomSearch">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" class="table-card" style="margin-bottom: 16px;">
          <template #header>
            <div class="card-header">
              <span>BOM版本管理</span>
              <div>
                <el-button type="primary" :icon="Plus" @click="handleAddVersion" style="margin-right: 8px;">创建版本</el-button>
                <el-button :icon="CopyDocument" @click="handleCopyVersion">复制版本</el-button>
              </div>
            </div>
          </template>
          <el-table v-loading="bomVersionLoading" :data="bomVersionList" border stripe style="width: 100%;">
            <el-table-column prop="product_code" label="产品编码" min-width="120" />
            <el-table-column prop="product_name" label="产品名称" min-width="150" />
            <el-table-column prop="version" label="版本号" width="100" align="center" />
            <el-table-column prop="status" label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="getStatusTagType(row.status)">{{ getStatusLabel(row.status) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ecn_code" label="ECN编号" min-width="120" />
            <el-table-column prop="effective_date" label="生效日期" width="120" />
            <el-table-column prop="description" label="描述" min-width="150" />
            <el-table-column label="操作" width="250" align="center">
              <template #default="{ row }">
                <el-button v-if="row.status === 'draft'" type="primary" link @click="handleActivateVersion(row)">生效</el-button>
                <el-button v-if="row.status === 'active'" type="warning" link @click="handleObsoleteVersion(row)">作废</el-button>
                <el-button v-if="row.status !== 'obsolete'" type="primary" link @click="selectVersion(row)">查看BOM</el-button>
                <el-button type="danger" link @click="handleDeleteVersion(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="card-header">
              <span>BOM列表</span>
              <el-button type="primary" :icon="Plus" @click="handleAddBom">新增BOM</el-button>
            </div>
          </template>
          <el-table v-loading="bomLoading" :data="bomList" border stripe>
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column prop="product_code" label="成品编码" min-width="120" />
            <el-table-column prop="product_name" label="成品名称" min-width="150" />
            <el-table-column prop="version" label="版本" width="80" align="center" />
            <el-table-column prop="level" label="层级" width="80" align="center" />
            <el-table-column prop="item_code" label="物料编码" min-width="120" />
            <el-table-column prop="item_name" label="物料名称" min-width="150" />
            <el-table-column prop="quantity" label="用量" width="100" align="center" />
            <el-table-column prop="unit" label="单位" width="80" align="center" />
            <el-table-column prop="scrap_rate" label="损耗率" width="100" align="center" />
            <el-table-column prop="drawing_code" label="装配图编号" min-width="120" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link :icon="Edit" @click="handleEditBom(row)">编辑</el-button>
                <el-button type="danger" link :icon="Delete" @click="handleDeleteBom(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="bomPagination.page"
              v-model:page-size="bomPagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="bomPagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchBomList"
              @current-change="fetchBomList"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="工作中心" name="workcenter">
        <el-card shadow="never" class="search-card">
          <el-form :inline="true" :model="wcSearch" class="search-form">
            <el-form-item label="编码">
              <el-input v-model="wcSearch.work_center_code" placeholder="请输入编码" clearable />
            </el-form-item>
            <el-form-item label="名称">
              <el-input v-model="wcSearch.work_center_name" placeholder="请输入名称" clearable />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="fetchWorkcenterList">搜索</el-button>
              <el-button :icon="Refresh" @click="resetWcSearch">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="card-header">
              <span>工作中心列表</span>
              <el-button type="primary" :icon="Plus" @click="handleAddWorkcenter">新增工作中心</el-button>
            </div>
          </template>
          <el-table v-loading="wcLoading" :data="wcList" border stripe>
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column prop="work_center_code" label="编码" min-width="120" />
            <el-table-column prop="work_center_name" label="名称" min-width="150" />
            <el-table-column prop="department" label="部门" min-width="100" />
            <el-table-column prop="location" label="位置" min-width="150" />
            <el-table-column prop="capacity" label="产能" width="80" align="center" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link :icon="Edit" @click="handleEditWorkcenter(row)">编辑</el-button>
                <el-button type="danger" link :icon="Delete" @click="handleDeleteWorkcenter(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="wcPagination.page"
              v-model:page-size="wcPagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="wcPagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchWorkcenterList"
              @current-change="fetchWorkcenterList"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="工序管理" name="process">
        <el-card shadow="never" class="search-card">
          <el-form :inline="true" :model="processSearch" class="search-form">
            <el-form-item label="工序编码">
              <el-input v-model="processSearch.process_code" placeholder="请输入编码" clearable />
            </el-form-item>
            <el-form-item label="工序名称">
              <el-input v-model="processSearch.process_name" placeholder="请输入名称" clearable />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="fetchProcessList">搜索</el-button>
              <el-button :icon="Refresh" @click="resetProcessSearch">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="card-header">
              <span>工序列表</span>
              <el-button type="primary" :icon="Plus" @click="handleAddProcess">新增工序</el-button>
            </div>
          </template>
          <el-table v-loading="processLoading" :data="processList" border stripe>
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column prop="process_code" label="工序编码" min-width="120" />
            <el-table-column prop="process_name" label="工序名称" min-width="150" />
            <el-table-column prop="process_type" label="工艺类型" width="100" align="center" />
            <el-table-column prop="sequence" label="顺序" width="80" align="center" />
            <el-table-column prop="work_center_code" label="工作中心" min-width="120" />
            <el-table-column prop="standard_time" label="标准工时(分钟)" width="140" align="center" />
            <el-table-column prop="drawing_code" label="图纸编号" min-width="120" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link :icon="Edit" @click="handleEditProcess(row)">编辑</el-button>
                <el-button type="danger" link :icon="Delete" @click="handleDeleteProcess(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="processPagination.page"
              v-model:page-size="processPagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="processPagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchProcessList"
              @current-change="fetchProcessList"
            />
          </div>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="工艺路线" name="route">
        <el-card shadow="never" class="search-card">
          <el-form :inline="true" :model="routeSearch" class="search-form">
            <el-form-item label="路线编码">
              <el-input v-model="routeSearch.route_code" placeholder="请输入编码" clearable />
            </el-form-item>
            <el-form-item label="路线名称">
              <el-input v-model="routeSearch.route_name" placeholder="请输入名称" clearable />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :icon="Search" @click="fetchRouteList">搜索</el-button>
              <el-button :icon="Refresh" @click="resetRouteSearch">重置</el-button>
            </el-form-item>
          </el-form>
        </el-card>
        <el-card shadow="never" class="table-card">
          <template #header>
            <div class="card-header">
              <span>工艺路线列表</span>
              <el-button type="primary" :icon="Plus" @click="handleAddRoute">新增工艺路线</el-button>
            </div>
          </template>
          <el-table v-loading="routeLoading" :data="routeList" border stripe>
            <el-table-column prop="id" label="ID" width="80" align="center" />
            <el-table-column prop="route_code" label="路线编码" min-width="120" />
            <el-table-column prop="route_name" label="路线名称" min-width="150" />
            <el-table-column prop="product_code" label="产品编码" min-width="120" />
            <el-table-column prop="product_name" label="产品名称" min-width="150" />
            <el-table-column prop="bom_code" label="关联BOM" min-width="120" />
            <el-table-column prop="bom_version" label="BOM版本" width="80" align="center" />
            <el-table-column prop="version" label="版本" width="80" align="center" />
            <el-table-column label="状态" width="100" align="center">
              <template #default="{ row }">
                <el-tag :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180" />
            <el-table-column label="操作" width="200" fixed="right" align="center">
              <template #default="{ row }">
                <el-button type="primary" link :icon="Edit" @click="handleEditRoute(row)">编辑</el-button>
                <el-button type="danger" link :icon="Delete" @click="handleDeleteRoute(row)">删除</el-button>
              </template>
            </el-table-column>
          </el-table>
          <div class="pagination-wrapper">
            <el-pagination
              v-model:current-page="routePagination.page"
              v-model:page-size="routePagination.pageSize"
              :page-sizes="[10, 20, 50, 100]"
              :total="routePagination.total"
              layout="total, sizes, prev, pager, next, jumper"
              @size-change="fetchRouteList"
              @current-change="fetchRouteList"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="700px" @close="resetForm">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="120px">
        <template v-if="activeTab === 'material'">
          <el-form-item label="物料编码" prop="material_code">
            <el-input v-model="formData.material_code" placeholder="请输入物料编码" />
          </el-form-item>
          <el-form-item label="物料名称" prop="material_name">
            <el-input v-model="formData.material_name" placeholder="请输入物料名称" />
          </el-form-item>
          <el-form-item label="物料类型" prop="material_type">
            <el-select v-model="formData.material_type" placeholder="请选择物料类型">
              <el-option label="原材料" value="raw" />
              <el-option label="成品" value="finished" />
              <el-option label="半成品" value="semi" />
              <el-option label="夹具" value="fixture" />
            </el-select>
          </el-form-item>
          <el-form-item label="规格型号">
            <el-input v-model="formData.specification" placeholder="请输入规格型号" />
          </el-form-item>
          <el-form-item label="图纸编号">
            <el-input v-model="formData.drawing_code" placeholder="请输入图纸编号" />
          </el-form-item>
          <el-form-item label="图纸文件">
            <el-input v-model="formData.drawing_url" placeholder="请输入图纸文件地址" />
          </el-form-item>
          <el-form-item label="计量单位" prop="unit">
            <el-input v-model="formData.unit" placeholder="请输入计量单位" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input type="textarea" v-model="formData.description" placeholder="请输入描述" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="formData.is_active" />
          </el-form-item>
        </template>
        <template v-else-if="activeTab === 'bom'">
          <el-form-item label="成品编码" prop="product_code">
            <el-input v-model="formData.product_code" placeholder="请输入成品编码" />
          </el-form-item>
          <el-form-item label="成品名称" prop="product_name">
            <el-input v-model="formData.product_name" placeholder="请输入成品名称" />
          </el-form-item>
          <el-form-item label="版本" prop="version">
            <el-input v-model="formData.version" placeholder="请输入版本号" />
          </el-form-item>
          <el-form-item label="层级" prop="level">
            <el-input-number v-model="formData.level" :min="1" :max="10" />
          </el-form-item>
          <el-form-item label="物料编码" prop="item_code">
            <el-input v-model="formData.item_code" placeholder="请输入物料编码" />
          </el-form-item>
          <el-form-item label="物料名称" prop="item_name">
            <el-input v-model="formData.item_name" placeholder="请输入物料名称" />
          </el-form-item>
          <el-form-item label="用量" prop="quantity">
            <el-input-number v-model="formData.quantity" :min="0.000001" :precision="6" />
          </el-form-item>
          <el-form-item label="单位" prop="unit">
            <el-input v-model="formData.unit" placeholder="请输入单位" />
          </el-form-item>
          <el-form-item label="装配图编号">
            <el-input v-model="formData.drawing_code" placeholder="请输入装配图编号" />
          </el-form-item>
          <el-form-item label="装配图文件">
            <el-input v-model="formData.drawing_url" placeholder="请输入装配图文件地址" />
          </el-form-item>
          <el-form-item label="损耗率">
            <el-input-number v-model="formData.scrap_rate" :min="0" :max="1" :precision="4" />
          </el-form-item>
          <el-form-item label="备注">
            <el-input type="textarea" v-model="formData.remark" placeholder="请输入备注" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="formData.is_active" />
          </el-form-item>
        </template>
        <template v-else-if="activeTab === 'workcenter'">
          <el-form-item label="工作中心编码" prop="work_center_code">
            <el-input v-model="formData.work_center_code" placeholder="请输入编码" />
          </el-form-item>
          <el-form-item label="工作中心名称" prop="work_center_name">
            <el-input v-model="formData.work_center_name" placeholder="请输入名称" />
          </el-form-item>
          <el-form-item label="所属部门">
            <el-input v-model="formData.department" placeholder="请输入部门" />
          </el-form-item>
          <el-form-item label="位置">
            <el-input v-model="formData.location" placeholder="请输入位置" />
          </el-form-item>
          <el-form-item label="产能" prop="capacity">
            <el-input-number v-model="formData.capacity" :min="1" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input type="textarea" v-model="formData.description" placeholder="请输入描述" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="formData.is_active" />
          </el-form-item>
        </template>

        <template v-else-if="activeTab === 'process'">
          <el-form-item label="工序编码" prop="process_code">
            <el-input v-model="formData.process_code" placeholder="请输入工序编码" />
          </el-form-item>
          <el-form-item label="工序名称" prop="process_name">
            <el-input v-model="formData.process_name" placeholder="请输入工序名称" />
          </el-form-item>
          <el-form-item label="工艺类型" prop="process_type">
            <el-select v-model="formData.process_type" placeholder="请选择工艺类型">
              <el-option label="机械加工" value="machining" />
              <el-option label="装配" value="assembly" />
              <el-option label="焊接" value="welding" />
              <el-option label="喷涂" value="painting" />
              <el-option label="检验" value="inspection" />
            </el-select>
          </el-form-item>
          <el-form-item label="工序顺序" prop="sequence">
            <el-input-number v-model="formData.sequence" :min="0" />
          </el-form-item>
          <el-form-item label="工作中心编码">
            <el-input v-model="formData.work_center_code" placeholder="请输入工作中心编码" />
          </el-form-item>
          <el-form-item label="标准工时(分钟)">
            <el-input-number v-model="formData.standard_time" :min="0" :precision="2" />
          </el-form-item>
          <el-form-item label="图纸编号">
            <el-input v-model="formData.drawing_code" placeholder="请输入图纸编号" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input type="textarea" v-model="formData.description" placeholder="请输入描述" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="formData.is_active" />
          </el-form-item>
        </template>

        <template v-else-if="activeTab === 'route'">
          <el-form-item label="路线编码" prop="route_code">
            <el-input v-model="formData.route_code" placeholder="请输入路线编码" />
          </el-form-item>
          <el-form-item label="路线名称" prop="route_name">
            <el-input v-model="formData.route_name" placeholder="请输入路线名称" />
          </el-form-item>
          <el-form-item label="产品编码" prop="product_code">
            <el-input v-model="formData.product_code" placeholder="请输入产品编码" />
          </el-form-item>
          <el-form-item label="产品名称" prop="product_name">
            <el-input v-model="formData.product_name" placeholder="请输入产品名称" />
          </el-form-item>
          <el-form-item label="关联BOM" prop="bom_code">
            <el-select v-model="formData.bom_code" placeholder="请选择关联BOM" @change="handleBomChange">
              <el-option v-for="bom in bomOptions" :key="bom.value + '-' + bom.version" :label="bom.label" :value="bom.value" :data="bom" />
            </el-select>
          </el-form-item>
          <el-form-item label="BOM版本">
            <el-input v-model="formData.bom_version" placeholder="BOM版本号" readonly />
          </el-form-item>
          <el-form-item label="版本" prop="version">
            <el-input v-model="formData.version" placeholder="请输入版本号" />
          </el-form-item>
          <el-form-item label="描述">
            <el-input type="textarea" v-model="formData.description" placeholder="请输入描述" />
          </el-form-item>
          <el-form-item label="状态">
            <el-switch v-model="formData.is_active" />
          </el-form-item>
          <el-form-item label="工序列表">
            <div class="route-process-container">
              <el-table :data="formData.processes || []" border size="small">
                <el-table-column label="序号" type="index" width="60" align="center" />
                <el-table-column label="工序编码" width="120">
                  <template #default="{ row }">
                    <el-input v-model="row.process_code" placeholder="工序编码" />
                  </template>
                </el-table-column>
                <el-table-column label="工序名称" width="150">
                  <template #default="{ row }">
                    <el-input v-model="row.process_name" placeholder="工序名称" />
                  </template>
                </el-table-column>
                <el-table-column label="工作中心" width="120">
                  <template #default="{ row }">
                    <el-input v-model="row.work_center_code" placeholder="工作中心编码" />
                  </template>
                </el-table-column>
                <el-table-column label="顺序" width="80">
                  <template #default="{ row }">
                    <el-input-number v-model="row.sequence" :min="1" size="small" />
                  </template>
                </el-table-column>
                <el-table-column label="操作" width="80" align="center">
                  <template #default="{ $index }">
                    <el-button type="danger" link size="small" @click="removeRouteProcess($index)">删除</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <el-button type="primary" size="small" :icon="Plus" @click="addRouteProcess" style="margin-top: 8px;">添加工序</el-button>
            </div>
          </el-form-item>
        </template>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitLoading" @click="handleSave">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Plus, Edit, Delete, CopyDocument } from '@element-plus/icons-vue'
import {
  getMaterialList, createMaterial, updateMaterial, deleteMaterial,
  getBomList, createBom, updateBom, deleteBom, getBomOptions,
  getBomVersionList, createBomVersion, copyBomVersion, activateBomVersion, obsoleteBomVersion,
  getWorkcenterList, createWorkcenter, updateWorkcenter, deleteWorkcenter,
  getProcessList, createProcess, updateProcess, deleteProcess,
  getRouteList, createRoute, updateRoute, deleteRoute, getRouteDetail
} from '@/api/mes'

const activeTab = ref('material')

const materialLoading = ref(false)
const materialList = ref([])
const materialSearch = reactive({ material_code: '', material_name: '' })
const materialPagination = reactive({ page: 1, pageSize: 10, total: 0 })

const bomLoading = ref(false)
const bomList = ref([])
const bomSearch = reactive({ product_code: '', item_code: '', version: '' })
const bomPagination = reactive({ page: 1, pageSize: 10, total: 0 })

const bomVersionLoading = ref(false)
const bomVersionList = ref([])
const bomVersionOptions = ref([])

const wcLoading = ref(false)
const wcList = ref([])
const wcSearch = reactive({ work_center_code: '', work_center_name: '' })
const wcPagination = reactive({ page: 1, pageSize: 10, total: 0 })

const processLoading = ref(false)
const processList = ref([])
const processSearch = reactive({ process_code: '', process_name: '' })
const processPagination = reactive({ page: 1, pageSize: 10, total: 0 })

const routeLoading = ref(false)
const routeList = ref([])
const routeSearch = reactive({ route_code: '', route_name: '' })
const routePagination = reactive({ page: 1, pageSize: 10, total: 0 })
const bomOptions = ref([])

const dialogVisible = ref(false)
const isEdit = ref(false)
const submitLoading = ref(false)
const formRef = ref(null)
const formData = reactive({})
const formRules = reactive({})

const dialogTitle = ref('')
const currentId = ref(null)

const getMaterialTypeName = (type) => {
  const map = { raw: '原材料', finished: '成品', semi: '半成品', fixture: '夹具' }
  return map[type] || type
}

const getMaterialTypeTag = (type) => {
  const map = { raw: 'success', finished: 'warning', semi: 'primary', fixture: 'info' }
  return map[type] || 'info'
}

const fetchMaterialList = async () => {
  materialLoading.value = true
  try {
    const res = await getMaterialList({
      page: materialPagination.page,
      page_size: materialPagination.pageSize,
      ...materialSearch
    })
    materialList.value = res.data.items || []
    materialPagination.total = res.data.total || 0
  } catch (e) { console.error('获取物料列表失败:', e) }
  finally { materialLoading.value = false }
}

const resetMaterialSearch = () => {
  materialSearch.material_code = ''
  materialSearch.material_name = ''
  materialPagination.page = 1
  fetchMaterialList()
}

const fetchBomList = async () => {
  bomLoading.value = true
  try {
    const res = await getBomList({
      page: bomPagination.page,
      page_size: bomPagination.pageSize,
      ...bomSearch
    })
    bomList.value = res.data.items || []
    bomPagination.total = res.data.total || 0
  } catch (e) { console.error('获取BOM列表失败:', e) }
  finally { bomLoading.value = false }
}

const resetBomSearch = () => {
  bomSearch.product_code = ''
  bomSearch.item_code = ''
  bomPagination.page = 1
  fetchBomList()
}

const fetchWorkcenterList = async () => {
  wcLoading.value = true
  try {
    const res = await getWorkcenterList({
      page: wcPagination.page,
      page_size: wcPagination.pageSize,
      ...wcSearch
    })
    wcList.value = res.data.items || []
    wcPagination.total = res.data.total || 0
  } catch (e) { console.error('获取工作中心列表失败:', e) }
  finally { wcLoading.value = false }
}

const resetWcSearch = () => {
  wcSearch.work_center_code = ''
  wcSearch.work_center_name = ''
  wcPagination.page = 1
  fetchWorkcenterList()
}

const fetchBomVersionList = async () => {
  bomVersionLoading.value = true
  try {
    const res = await getBomVersionList({})
    bomVersionList.value = res.data.items || res.data || []
    bomVersionOptions.value = bomVersionList.value.map(v => ({
      version: v.version,
      label: `${v.product_code} - ${v.version}`
    }))
  } catch (e) { console.error('获取BOM版本列表失败:', e) }
  finally { bomVersionLoading.value = false }
}

const getStatusLabel = (status) => {
  const labels = { draft: '草稿', active: '生效', obsolete: '作废' }
  return labels[status] || status
}

const getStatusTagType = (status) => {
  const types = { draft: 'info', active: 'success', obsolete: 'warning' }
  return types[status] || 'info'
}

const handleAddVersion = () => {
  ElMessageBox.prompt('请输入版本号:', '创建版本', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    inputPattern: /^V?\d+\.\d+$/,
    inputErrorMessage: '版本号格式错误，如 V1.0 或 1.0'
  }).then(async ({ value }) => {
    const product_code = bomSearch.product_code || prompt('请输入产品编码:')
    if (!product_code) return
    
    try {
      await createBomVersion({
        product_code,
        version: value,
        product_name: prompt('请输入产品名称:') || ''
      })
      ElMessage.success('版本创建成功')
      fetchBomVersionList()
    } catch (e) {
      ElMessage.error(e.response?.data?.detail || '创建失败')
    }
  }).catch(() => {})
}

const handleCopyVersion = () => {
  const rows = bomVersionList.value.filter(v => v.status !== 'obsolete')
  if (rows.length === 0) {
    ElMessage.warning('没有可复制的版本')
    return
  }
  
  const names = rows.map(v => `${v.product_code} - ${v.version}`).join('\n')
  ElMessageBox.prompt(`请选择源版本:\n${names}\n\n输入源版本号:`, '复制版本', {
    confirmButtonText: '确定',
    cancelButtonText: '取消'
  }).then(async ({ value }) => {
    const source = rows.find(v => v.version === value)
    if (!source) {
      ElMessage.error('源版本不存在')
      return
    }
    
    ElMessageBox.prompt('请输入新版本号:', '复制版本', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPattern: /^V?\d+\.\d+$/,
      inputErrorMessage: '版本号格式错误'
    }).then(async ({ value: newVersion }) => {
      try {
        await copyBomVersion(source.id, { new_version: newVersion })
        ElMessage.success('版本复制成功')
        fetchBomVersionList()
      } catch (e) {
        ElMessage.error(e.response?.data?.detail || '复制失败')
      }
    }).catch(() => {})
  }).catch(() => {})
}

const handleActivateVersion = async (row) => {
  try {
    await activateBomVersion(row.id)
    ElMessage.success('版本已生效')
    fetchBomVersionList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

const handleObsoleteVersion = async (row) => {
  try {
    await obsoleteBomVersion(row.id)
    ElMessage.success('版本已作废')
    fetchBomVersionList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '操作失败')
  }
}

const handleDeleteVersion = async (row) => {
  await ElMessageBox.confirm(`确定删除版本 ${row.version}?`, '提示', {
    confirmButtonText: '确定',
    cancelButtonText: '取消',
    type: 'warning'
  })
  try {
    await obsoleteBomVersion(row.id)
    ElMessage.success('版本已删除')
    fetchBomVersionList()
  } catch (e) {
    ElMessage.error(e.response?.data?.detail || '删除失败')
  }
}

const selectVersion = (row) => {
  bomSearch.product_code = row.product_code
  bomSearch.version = row.version
  fetchBomList()
}

const fetchProcessList = async () => {
  processLoading.value = true
  try {
    const res = await getProcessList({
      page: processPagination.page,
      page_size: processPagination.pageSize,
      ...processSearch
    })
    processList.value = res.data.items || []
    processPagination.total = res.data.total || 0
  } catch (e) { console.error('获取工序列表失败:', e) }
  finally { processLoading.value = false }
}

const resetProcessSearch = () => {
  processSearch.process_code = ''
  processSearch.process_name = ''
  processPagination.page = 1
  fetchProcessList()
}

const fetchRouteList = async () => {
  routeLoading.value = true
  try {
    const res = await getRouteList({
      page: routePagination.page,
      page_size: routePagination.pageSize,
      ...routeSearch
    })
    routeList.value = res.data.items || []
    routePagination.total = res.data.total || 0
  } catch (e) { console.error('获取工艺路线列表失败:', e) }
  finally { routeLoading.value = false }
}

const fetchBomOptions = async () => {
  try {
    const res = await getBomOptions()
    bomOptions.value = res.data || []
  } catch (e) { console.error('获取BOM选项失败:', e) }
}

const handleBomChange = (value) => {
  const bom = bomOptions.value.find(b => b.value === value)
  if (bom) {
    formData.bom_version = bom.version
  } else {
    formData.bom_version = ''
  }
}

const resetRouteSearch = () => {
  routeSearch.route_code = ''
  routeSearch.route_name = ''
  routePagination.page = 1
  fetchRouteList()
}

const handleTabChange = async (tab) => {
  activeTab.value = tab
  if (tab === 'bom') {
    await fetchBomVersionList()
  }
}

const initForm = () => {
  Object.keys(formData).forEach(key => delete formData[key])
  Object.keys(formRules).forEach(key => delete formRules[key])
}

const resetMaterialForm = () => {
  formData.id = null
  formData.material_code = ''
  formData.material_name = ''
  formData.material_type = 'raw'
  formData.specification = ''
  formData.unit = ''
  formData.description = ''
  formData.is_active = true
  formRules.material_code = [{ required: true, message: '请输入物料编码', trigger: 'blur' }]
  formRules.material_name = [{ required: true, message: '请输入物料名称', trigger: 'blur' }]
  formRules.material_type = [{ required: true, message: '请选择物料类型', trigger: 'change' }]
  formRules.unit = [{ required: true, message: '请输入计量单位', trigger: 'blur' }]
}

const resetBomForm = () => {
  formData.id = null
  formData.product_code = bomSearch.product_code || ''
  formData.product_name = ''
  formData.version = bomSearch.version || 'V1.0'
  formData.level = 1
  formData.item_code = ''
  formData.item_name = ''
  formData.quantity = 1
  formData.unit = ''
  formData.scrap_rate = 0
  formData.remark = ''
  formData.is_active = true
  formRules.product_code = [{ required: true, message: '请输入成品编码', trigger: 'blur' }]
  formRules.product_name = [{ required: true, message: '请输入成品名称', trigger: 'blur' }]
  formRules.item_code = [{ required: true, message: '请输入物料编码', trigger: 'blur' }]
  formRules.item_name = [{ required: true, message: '请输入物料名称', trigger: 'blur' }]
  formRules.quantity = [{ required: true, message: '请输入用量', trigger: 'blur' }]
  formRules.unit = [{ required: true, message: '请输入单位', trigger: 'blur' }]
}

const resetWcForm = () => {
  formData.id = null
  formData.work_center_code = ''
  formData.work_center_name = ''
  formData.department = ''
  formData.location = ''
  formData.capacity = 1
  formData.description = ''
  formData.is_active = true
  formRules.work_center_code = [{ required: true, message: '请输入工作中心编码', trigger: 'blur' }]
  formRules.work_center_name = [{ required: true, message: '请输入工作中心名称', trigger: 'blur' }]
  formRules.capacity = [{ required: true, message: '请输入产能', trigger: 'blur' }]
}

const resetProcessForm = () => {
  formData.id = null
  formData.process_code = ''
  formData.process_name = ''
  formData.process_type = 'machining'
  formData.sequence = 0
  formData.work_center_code = ''
  formData.standard_time = 0
  formData.description = ''
  formData.is_active = true
  formRules.process_code = [{ required: true, message: '请输入工序编码', trigger: 'blur' }]
  formRules.process_name = [{ required: true, message: '请输入工序名称', trigger: 'blur' }]
  formRules.process_type = [{ required: true, message: '请选择工艺类型', trigger: 'change' }]
}

const resetRouteForm = () => {
  formData.id = null
  formData.route_code = ''
  formData.route_name = ''
  formData.product_code = ''
  formData.product_name = ''
  formData.bom_code = ''
  formData.bom_version = ''
  formData.version = 'V1.0'
  formData.description = ''
  formData.is_active = true
  formData.processes = []
  formRules.route_code = [{ required: true, message: '请输入路线编码', trigger: 'blur' }]
  formRules.route_name = [{ required: true, message: '请输入路线名称', trigger: 'blur' }]
  formRules.product_code = [{ required: true, message: '请输入产品编码', trigger: 'blur' }]
  formRules.product_name = [{ required: true, message: '请输入产品名称', trigger: 'blur' }]
}

const addRouteProcess = () => {
  formData.processes.push({
    process_code: '',
    process_name: '',
    work_center_code: '',
    work_center_name: '',
    sequence: (formData.processes.length || 0) + 1
  })
}

const removeRouteProcess = (index) => {
  formData.processes.splice(index, 1)
}

const handleAddMaterial = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增物料'
  resetMaterialForm()
  dialogVisible.value = true
}

const handleEditMaterial = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑物料'
  resetMaterialForm()
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleDeleteMaterial = (row) => {
  ElMessageBox.confirm('确定删除该物料？', '提示', { type: 'warning' }).then(async () => {
    await deleteMaterial(row.id)
    ElMessage.success('删除成功')
    fetchMaterialList()
  }).catch(() => {})
}

const handleAddBom = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增BOM'
  resetBomForm()
  dialogVisible.value = true
}

const handleEditBom = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑BOM'
  resetBomForm()
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleDeleteBom = (row) => {
  ElMessageBox.confirm('确定删除该BOM？', '提示', { type: 'warning' }).then(async () => {
    await deleteBom(row.id)
    ElMessage.success('删除成功')
    fetchBomList()
  }).catch(() => {})
}

const handleAddWorkcenter = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增工作中心'
  resetWcForm()
  dialogVisible.value = true
}

const handleEditWorkcenter = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑工作中心'
  resetWcForm()
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleDeleteWorkcenter = (row) => {
  ElMessageBox.confirm('确定删除该工作中心？', '提示', { type: 'warning' }).then(async () => {
    await deleteWorkcenter(row.id)
    ElMessage.success('删除成功')
    fetchWorkcenterList()
  }).catch(() => {})
}

const handleAddProcess = () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增工序'
  resetProcessForm()
  dialogVisible.value = true
}

const handleEditProcess = (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑工序'
  resetProcessForm()
  Object.assign(formData, row)
  dialogVisible.value = true
}

const handleDeleteProcess = (row) => {
  ElMessageBox.confirm('确定删除该工序？', '提示', { type: 'warning' }).then(async () => {
    await deleteProcess(row.id)
    ElMessage.success('删除成功')
    fetchProcessList()
  }).catch(() => {})
}

const handleAddRoute = async () => {
  isEdit.value = false
  currentId.value = null
  dialogTitle.value = '新增工艺路线'
  resetRouteForm()
  await fetchBomOptions()
  dialogVisible.value = true
}

const handleEditRoute = async (row) => {
  isEdit.value = true
  currentId.value = row.id
  dialogTitle.value = '编辑工艺路线'
  resetRouteForm()
  Object.assign(formData, row)
  
  await fetchBomOptions()
  
  try {
    const res = await getRouteDetail(row.id)
    if (res.data && res.data.processes) {
      formData.processes = res.data.processes
    }
  } catch (e) {
    console.error('获取工艺路线详情失败:', e)
  }
  
  dialogVisible.value = true
}

const handleDeleteRoute = (row) => {
  ElMessageBox.confirm('确定删除该工艺路线？', '提示', { type: 'warning' }).then(async () => {
    await deleteRoute(row.id)
    ElMessage.success('删除成功')
    fetchRouteList()
  }).catch(() => {})
}

const handleSave = async () => {
  await formRef.value.validate()
  submitLoading.value = true
  try {
    if (isEdit.value) {
      if (activeTab.value === 'material') await updateMaterial(currentId.value, formData)
      else if (activeTab.value === 'bom') await updateBom(currentId.value, formData)
      else if (activeTab.value === 'workcenter') await updateWorkcenter(currentId.value, formData)
      else if (activeTab.value === 'process') await updateProcess(currentId.value, formData)
      else if (activeTab.value === 'route') await updateRoute(currentId.value, formData)
      ElMessage.success('更新成功')
    } else {
      if (activeTab.value === 'material') await createMaterial(formData)
      else if (activeTab.value === 'bom') await createBom(formData)
      else if (activeTab.value === 'workcenter') await createWorkcenter(formData)
      else if (activeTab.value === 'process') await createProcess(formData)
      else if (activeTab.value === 'route') await createRoute(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    if (activeTab.value === 'material') fetchMaterialList()
    else if (activeTab.value === 'bom') fetchBomList()
    else if (activeTab.value === 'workcenter') fetchWorkcenterList()
    else if (activeTab.value === 'process') fetchProcessList()
    else if (activeTab.value === 'route') fetchRouteList()
  } catch (e) {
    console.error('提交失败:', e)
  } finally {
    submitLoading.value = false
  }
}

const resetForm = () => {
  formRef.value?.resetFields()
}

onMounted(() => {
  fetchMaterialList()
})
</script>

<style lang="scss" scoped>
.mes-base {
  .search-card { margin-bottom: 16px;
    .search-form { display: flex; flex-wrap: wrap;
      .el-form-item { margin-bottom: 0; margin-right: 16px; }
    }
  }
  .table-card {
    .card-header { display: flex; justify-content: space-between; align-items: center; }
  }
  .pagination-wrapper { margin-top: 16px; display: flex; justify-content: flex-end; }
}
</style>


