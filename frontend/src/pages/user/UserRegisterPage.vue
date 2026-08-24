<template>
  <div id="userRegisterPage">
    <h2 class="title">鱼皮 AI 应用生成 - 用户注册</h2>
    <div class="desc">不写一行代码，生成完整应用</div>
    <a-form :model="formState" name="basic" autocomplete="off" @finish="handleSubmit">
      <a-form-item name="user_name" :rules="[{ required: true, message: '请输入用户名' }]">
        <a-input v-model:value="formState.user_name" placeholder="请输入用户名" />
      </a-form-item>
      <a-form-item
        name="user_password"
        :rules="[
          { required: true, message: '请输入密码' },
          { min: 6, message: '密码不能小于 6 位' },
        ]"
      >
        <a-input-password v-model:value="formState.user_password" placeholder="请输入密码" />
      </a-form-item>
      <a-form-item
        name="confirm_password"
        :rules="[
          { required: true, message: '请确认密码' },
          { min: 6, message: '密码不能小于 6 位' },
          { validator: validateConfirmPassword },
        ]"
      >
        <a-input-password v-model:value="formState.confirm_password" placeholder="请确认密码" />
      </a-form-item>
      <div class="tips">
        已有账号？
        <RouterLink to="/user/login">去登录</RouterLink>
      </div>
      <a-form-item>
        <a-button type="primary" html-type="submit" style="width: 100%">注册并登录</a-button>
      </a-form-item>
    </a-form>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { userRegister } from '@/api/userController.ts'
import { message } from 'ant-design-vue'
import { reactive } from 'vue'
import { useLoginUserStore } from '@/stores/loginUser.ts'

const router = useRouter()

const formState = reactive<API.UserRegisterRequest>({
  user_name: '',
  user_password: '',
  confirm_password: '',
})

/**
 * 验证确认密码
 * @param rule
 * @param value
 * @param callback
 */
const validateConfirmPassword = (rule: unknown, value: string, callback: (error?: Error) => void) => {
  if (value && value !== formState.user_password) {
    callback(new Error('两次输入密码不一致'))
  } else {
    callback()
  }
}


const loginUserStore = useLoginUserStore()

/**
 * 提交表单
 * @param values
 */
const handleSubmit = async (values: API.UserRegisterRequest) => {
  const res = await userRegister(values)
  // 注册成功，跳转到登录页面
  if (res.data.code === 20000 && res.data.data) {
    message.success('注册成功')
    // 保存 access_token
    if (res.data.data.token) {
      loginUserStore.setToken(res.data.data.token)
    }
    // 获取完整登录用户信息，此时Cookie中的refresh token已经由浏览器自动保存
    await loginUserStore.fetchLoginUser()
    // TODO 调试待删除
    console.log('准备跳转到主页')
    console.log('login user id:' + loginUserStore.loginUser.id)
    console.log('login user name:' + loginUserStore.loginUser.user_name)
    // 跳转到注册前前页面（如果有redirect参数），否则跳到首页
    const redirect = router.currentRoute.value.query.redirect as string
    if (redirect) {
      router.push(redirect)
    } else {
      router.push({ path: '/', replace: true })
    }
  } else {
    message.error('注册失败，' + res.data.message)
  }
}
</script>

<style scoped>
#userRegisterPage {
  background: white;
  max-width: 720px;
  padding: 24px;
  margin: 24px auto;
}

.title {
  text-align: center;
  margin-bottom: 16px;
}

.desc {
  text-align: center;
  color: #bbb;
  margin-bottom: 16px;
}

.tips {
  margin-bottom: 16px;
  color: #bbb;
  font-size: 13px;
  text-align: right;
}
</style>
