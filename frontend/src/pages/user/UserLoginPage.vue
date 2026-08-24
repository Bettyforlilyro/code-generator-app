<template>
  <div id="userLoginPage">
    <h2 class="title">鱼皮 AI 应用生成 - 用户登录</h2>
    <div class="desc">不写一行代码，生成完整应用</div>
    <a-form :model="formState" name="basic" autocomplete="off" @finish="handleSubmit">
      <a-form-item name="user_name" :rules="[{ required: true, message: '请输入用户名' }]">
        <a-input v-model:value="formState.user_name" placeholder="请输入用户名" />
      </a-form-item>
      <a-form-item
        name="user_password"
        :rules="[
          { required: true, message: '请输入密码' },
          { min: 6, message: '密码长度不能小于 6 位' },
        ]"
      >
        <a-input-password v-model:value="formState.user_password" placeholder="请输入密码" />
      </a-form-item>
      <div class="tips">
        没有账号
        <RouterLink to="/user/register">去注册</RouterLink>
      </div>
      <a-form-item>
        <a-button type="primary" html-type="submit" style="width: 100%">登录</a-button>
      </a-form-item>
    </a-form>
  </div>
</template>
<script lang="ts" setup>
import { reactive } from 'vue'
import { getLoginUser, userLogin } from '@/api/userController.ts'
import { useLoginUserStore } from '@/stores/loginUser.ts'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'

const formState = reactive<API.UserLoginRequest>({
  user_name: '',
  user_password: '',
})

const router = useRouter()
const loginUserStore = useLoginUserStore()

/**
 * 提交表单
 * @param values
 */
const handleSubmit = async (values: any) => {
  const res = await userLogin(values)
  // TODO 调试待删除：打印完整响应查看实际结构
  console.log('登录API响应:', res)
  // 登录成功，把登录态保存到全局状态中
  if (res.data.code === 20000 && res.data.data) {
    // 保存 access_token
    if (res.data.data.token) {
      loginUserStore.setToken(res.data.data.token)
    }
    // 获取完整登录用户信息，此时Cookie中的refresh token已经由浏览器自动保存
    await loginUserStore.fetchLoginUser()
    message.success('登录成功')
    // TODO 调试待删除：确认路由跳转代码执行
    console.log('准备跳转到主页')
    console.log('login user id:' + loginUserStore.loginUser.id)
    console.log('login user name:' + loginUserStore.loginUser.user_name)
    // 跳转到登录前页面（如果有redirect参数），否则跳到首页
    const redirect = router.currentRoute.value.query.redirect as string
    if (redirect) {
      router.push(redirect)
    } else {
      router.push({ path: '/', replace: true })
    }
  } else {
    message.error('登录失败，' + res.data.message)
    // 清空已输入的账号和密码
    formState.user_name = ''
    formState.user_password = ''
  }
}
</script>

<style scoped>
#userLoginPage {
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
  text-align: right;
  color: #bbb;
  font-size: 13px;
  margin-bottom: 16px;
}
</style>
