<script lang="ts">
  import { LoaderCircle, Search } from '@lucide/svelte'
  import type { Snippet } from 'svelte'

  interface Props {
    query: string
    placeholder: string
    disabled: boolean
    loading: boolean
    status: string
    /** 검색은 Enter·검색 버튼으로만 실행 (입력 중 자동 검색 없음 — 의도된 기존 동작) */
    onSearch: () => void
    /** 검색 버튼 옆 추가 도구 (필터 등) */
    tools?: Snippet
    children: Snippet
    list?: HTMLElement
  }

  let {
    query = $bindable(),
    placeholder,
    disabled,
    loading,
    status,
    onSearch,
    tools,
    children,
    list = $bindable(),
  }: Props = $props()
</script>

<div class="search panel">
  <form
    class="bar"
    onsubmit={(e) => {
      e.preventDefault()
      onSearch()
    }}
  >
    <label class="input">
      <Search size={16} />
      <input class="field" {placeholder} {disabled} bind:value={query} />
    </label>
    <button type="submit" class="btn" {disabled}>검색</button>
    {@render tools?.()}
  </form>

  <p class="status faint">
    {#if loading}<LoaderCircle size={13} class="spin" />{/if}
    {status}
  </p>

  <div class="list" bind:this={list}>
    {@render children()}
  </div>
</div>

<style>
  .search {
    position: relative; /* 필터 창 등 떠 있는 도구의 기준 */
    display: grid;
    grid-template-rows: auto auto 1fr;
    min-height: 0;
    padding: 14px 10px 10px 14px;
  }

  .bar {
    display: flex;
    gap: 8px;
    padding-right: 4px;
  }

  .input {
    position: relative;
    flex: 1;
    min-width: 0;
  }

  .input :global(svg) {
    position: absolute;
    left: 11px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-3);
    pointer-events: none;
  }

  .input .field {
    padding-left: 34px;
  }

  .bar :global(.btn) {
    height: 36px;
  }

  .status {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 4px 8px;
  }

  .list {
    display: grid;
    align-content: start;
    gap: 2px;
    min-height: 0;
    overflow-y: auto;
    padding-right: 4px;
  }
</style>
