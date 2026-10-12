import { mount } from 'svelte'
import 'pretendard/dist/web/variable/pretendardvariable-dynamic-subset.css'
import './app.css'
import App from './App.svelte'

// 이미지 드롭 영역 밖에 파일을 떨어뜨려도 웹뷰가 그 파일로 이동하지 않게
for (const type of ['dragover', 'drop'] as const) {
  window.addEventListener(type, (event) => event.preventDefault())
}

mount(App, { target: document.getElementById('app')! })
