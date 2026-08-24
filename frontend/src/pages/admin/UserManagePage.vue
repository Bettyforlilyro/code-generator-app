<template>
  <div id="userManagePage">
    <!-- 搜索表单 -->
    <a-form layout="inline" :model="searchParams" @finish="doSearch">
      <a-form-item label="账号">
        <a-input v-model:value="searchParams.user_account" placeholder="输入账号" />
      </a-form-item>
      <a-form-item label="用户名">
        <a-input v-model:value="searchParams.user_name" placeholder="输入用户名" />
      </a-form-item>
      <a-form-item label="角色权限">
        <a-select
          v-model:value="searchParams.user_role"
          placeholder="选择角色权限"
          allow-clear
          style="width: 150px"
        >
          <a-select-option value="admin">管理员</a-select-option>
          <a-select-option value="user">普通用户</a-select-option>
        </a-select>
      </a-form-item>
      <a-form-item>
        <a-button type="primary" html-type="submit">搜索</a-button>
      </a-form-item>
      <a-form-item>
        <a-button type="primary" @click="openAddUserModal">添加用户</a-button>
      </a-form-item>
    </a-form>
    <a-divider />
    <!-- 表格 -->
    <a-table
      :columns="columns"
      :data-source="data"
      :pagination="pagination"
      @change="doTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.dataIndex === 'user_avatar'">
          <a-image :src="record.user_avatar" :width="120" />
        </template>
        <template v-else-if="column.dataIndex === 'user_role'">
          <div v-if="record.user_role === 'admin'">
            <a-tag color="green">管理员</a-tag>
          </div>
          <div v-else>
            <a-tag color="blue">普通用户</a-tag>
          </div>
        </template>
        <template v-else-if="column.dataIndex === 'create_time'">
          {{ dayjs(record.create_time).format('YYYY-MM-DD HH:mm:ss') }}
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button type="primary" @click="doEdit(record)">编辑</a-button>
          <a-button danger @click="doDelete(record.id)">删除</a-button>
        </template>
      </template>
    </a-table>
    <!-- 编辑用户弹窗 -->
    <a-modal
      v-model:open="editModalVisible"
      title="编辑用户"
      @ok="doSubmitEdit"
      ok-text="保存"
      cancel-text="取消"
    >
      <a-form :model="editForm" layout="vertical">
        <a-form-item label="简介">
          <a-textarea v-model:value="editForm.user_profile" placeholder="请输入简介" :rows="3" />
        </a-form-item>
        <a-form-item label="角色权限">
          <a-select v-model:value="editForm.user_role" placeholder="请选择角色">
            <a-select-option value="admin">管理员</a-select-option>
            <a-select-option value="user">普通用户</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
    <!-- 添加用户弹窗 -->
    <a-modal
      v-model:open="addModalVisible"
      title="添加用户"
      @ok="doSubmitAdd"
      ok-text="保存"
      cancel-text="取消"
    >
      <a-form :model="addForm" layout="vertical">
        <a-form-item label="用户名">
          <a-input v-model:value="addForm.user_name" placeholder="请输入用户名" />
        </a-form-item>
        <a-form-item label="密码">
          <a-input v-model:value="addForm.user_password" placeholder="请输入密码" />
        </a-form-item>
        <a-form-item label="角色权限">
          <a-select v-model:value="addForm.user_role" placeholder="请选择角色">
            <a-select-option value="admin">管理员</a-select-option>
            <a-select-option value="user">普通用户</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>
<script lang="ts" setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { addUser, deleteUser, listUserVoByPage, updateUser } from '@/api/userController.ts'
import { message, Modal } from 'ant-design-vue'
import dayjs from 'dayjs'
import { useLoginUserStore } from '@/stores/loginUser.ts'

const loginUserStore = useLoginUserStore()


const columns = [
  {
    title: 'id',
    dataIndex: 'user_name',
    sorter: true,
  },
  {
    title: '头像',
    dataIndex: 'user_avatar',
  },
  {
    title: '简介',
    dataIndex: 'user_profile',
  },
  {
    title: '用户角色',
    dataIndex: 'user_role',
    sorter: true,
  },
  {
    title: '创建时间',
    dataIndex: 'create_time',
    sorter: true,
  },
  {
    title: '操作',
    key: 'action',
  },
]

// 展示的数据
const data = ref<API.UserVO[]>([])
const total = ref(0)


// 搜索条件：当前页码、每页数量
const searchParams = reactive<API.UserQueryRequest>({
  page: 1,
  per_page: 5,
})

// 获取数据
const fetchData = async () => {
  // TODO 调试待删除
  console.log('searchParams: ' + JSON.stringify(searchParams))
  const res = await listUserVoByPage({
    ...searchParams,
  })
  if (res.data.data) {
    data.value = res.data.data.users ?? []
    total.value = res.data.data.total ?? 0
  } else {
    message.error('获取数据失败，' + res.data.message)
  }
}

// 分页参数
const pagination = computed(() => {
  return {
    current: searchParams.page ?? 1,
    pageSize: searchParams.per_page ?? 10,
    total: total.value,
    showSizeChanger: true,
    showTotal: (total: number) => `共 ${total} 条`,
  }
})

// 表格变化时的操作（分页、排序）
const doTableChange = (
  page: { current: number; pageSize: number },
  _filters: any,
  sorter: { field: string; order: string | null }
) => {
  // 分页变化
  searchParams.page = page.current
  searchParams.per_page = page.pageSize
  // 排序变化
  if (sorter.order) {
    searchParams.sort_field = sorter.field
    searchParams.sort_order = sorter.order === 'ascend' ? 'asc' : 'desc'
  } else {
    // 取消排序时，清空排序参数
    searchParams.sort_field = undefined
    searchParams.sort_order = undefined
  }
  fetchData()
}

// 搜索数据
const doSearch = () => {
  // 重置页码
  searchParams.page = 1
  fetchData()
}

// 编辑用户信息，只能修改简介和角色权限
const editModalVisible = ref(false)
const editForm = reactive<API.UserUpdateRequest>({
  id: undefined,
  user_name: undefined,
  user_avatar: undefined,
  user_profile: '',
  user_role: '',
})

// 打开编辑弹窗
const doEdit = (record: API.UserVO) => {
  editForm.id = record.id
  editForm.user_name = record.user_name ?? ''
  editForm.user_avatar = record.user_avatar ?? ''
  editForm.user_profile = record.user_profile ?? ''
  editForm.user_role = record.user_role ?? ''
  editModalVisible.value = true
}

// 提交编辑
const doSubmitEdit = async () => {
  if (!editForm.id) {
    message.error('用户ID不存在')
    return
  }
  // 不允许修改自己的权限
  if (Number(editForm.id) === loginUserStore.loginUser.id
    && editForm.user_role !== loginUserStore.loginUser.user_role) {
    Modal.warning({
      title: '无法修改',
      content: '您不能修改自己的权限！',
      okText: '我知道了',
    })
    return
  }
  const res = await updateUser({
    id: editForm.id,
    user_name: editForm.user_name,
    user_avatar: editForm.user_avatar,
    user_profile: editForm.user_profile,
    user_role: editForm.user_role,
  })
  if (res.data.code === 20000) {
    message.success('修改成功')
    editModalVisible.value = false
    fetchData()
  } else {
    message.error('修改失败：' + res.data.message)
  }
}

// 新增用户弹窗相关
const addModalVisible = ref(false)
const addForm = reactive<API.UserAddRequest>({
  user_name: '',
  user_password: '',
  user_role: 'user',
})

// 打开新增弹窗
const openAddUserModal = () => {
  addForm.user_name = ''
  addForm.user_password = ''
  addForm.user_role = 'user'
  addModalVisible.value = true
}

// 提交新增用户
const doSubmitAdd = async () => {
  if (!addForm.user_name) {
    message.error('请输入用户名')
    return
  }
  if (!addForm.user_password) {
    message.error('请输入密码')
    return
  }
  const res = await addUser({
    user_name: addForm.user_name,
    user_password: addForm.user_password,
    confirm_password: addForm.user_password,
    user_role: addForm.user_role,
  })
  if (res.data.code === 20000) {
    message.success('新增成功')
    addModalVisible.value = false
    fetchData()
  } else {
    message.error('新增失败：' + res.data.message)
  }
}
// 删除数据
const doDelete = async (id: number) => {
  if (!id) {
    return
  }
  // 不允许删除自己
  if (Number(id) === loginUserStore.loginUser.id) {
    Modal.warning({
      title: '无法删除',
      content: '您不能删除自己的账号！',
      okText: '我知道了',
    })
    return
  }
  Modal.confirm({
    title: '确认删除',
    content: '确定要删除这个用户吗？此操作不可恢复。',
    okText: '确认删除',
    cancelText: '取消',
    okButtonProps: { danger: true },
    onOk: async () => {
      const res = await deleteUser({ id })
      if (res.data.code === 20000) {
        message.success('删除成功')
        // 刷新数据
        fetchData()
      } else {
        message.error('删除失败：' + res.data.message)
      }
    },
  })
}

// 页面加载时请求一次
onMounted(() => {
  fetchData()
})
</script>

<style scoped>
#userManagePage {
  padding: 24px;
  background: white;
  margin-top: 16px;
}
</style>
