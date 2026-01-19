<template>
  <n-config-provider :theme="null" :theme-overrides="themeOverrides">
    <RouterView />
  </n-config-provider>
</template>

<script setup lang="ts">
import { RouterView } from 'vue-router'
import { NConfigProvider } from 'naive-ui'

const themeOverrides = {
  common: {
    primaryColor: '#9b7cb9',
    primaryColorHover: '#a58cc3',
    primaryColorPressed: '#8a6ba8',
    infoColor: '#9b7cb9',
    successColor: '#10b981',
    warningColor: '#f59e0b',
    errorColor: '#e8927c',
    borderColor: '#e0d8c8',
    bodyColor: '#f8f4e6',
    cardColor: '#fffaf0',
    modalColor: '#fffaf0',
    popoverColor: '#fffaf0',
    tableColor: '#fffaf0',
    textColorBase: '#333333',
    textColor1: '#333333',
    textColor2: '#666666',
  },
  Layout: {
    color: 'transparent',
    headerColor: 'transparent',
    siderColor: 'transparent',
  },
  Card: {
    borderRadius: '12px',
    color: '#fffaf0',
    borderColor: '#e0d8c8',
  },
  Button: {
    borderRadiusSmall: '8px',
    borderRadiusMedium: '10px',
    borderRadiusLarge: '12px',
  },
  Input: {
    borderRadius: '8px',
    color: 'transparent',
    borderColor: '#e0d8c8',
  },
  Tag: {
    borderRadius: '6px',
  },
}
</script>
