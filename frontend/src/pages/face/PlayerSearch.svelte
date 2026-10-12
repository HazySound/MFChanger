<script lang="ts">
  import { SlidersHorizontal } from '@lucide/svelte'
  import { tick } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import SearchPanel from '../../lib/components/SearchPanel.svelte'
  import {
    cardsOfPid,
    emptyFilter,
    groupByPlayer,
    isFilterActive,
    meta,
    pidOf,
    searchCards,
    type SeasonFilter as Filter,
  } from '../../lib/meta.svelte'
  import type { Player } from '../../lib/types'
  import CardGroup from './CardGroup.svelte'
  import SeasonFilter from './SeasonFilter.svelte'

  interface Props {
    selectedSpid: number | null
    onSelect: (card: Player) => void
  }

  let { selectedSpid, onSelect }: Props = $props()

  let query = $state('')
  /** 마지막으로 검색한 검색어 — 상태 문구는 입력 중인 글자가 아니라 이 값을 기준으로 */
  let searchedQuery = $state('')
  let filter = $state<Filter>(emptyFilter())
  let filterOpen = $state(false)
  let results = $state.raw<Player[]>([])
  /** 파일명으로 특정 선수만 보여줄 때 그 pid */
  let pidLabel = $state<number | null>(null)
  const expanded = new SvelteSet<number>()
  let list = $state<HTMLElement>()

  const groups = $derived(groupByPlayer(results))
  const filterActive = $derived(isFilterActive(filter))

  const status = $derived.by(() => {
    if (meta.error) return `선수 데이터를 불러오지 못했습니다: ${meta.error}`
    if (!meta.loaded) return '선수 데이터를 불러오는 중...'
    if (pidLabel !== null) return `PID ${pidLabel} 선수의 카드 ${results.length}장`
    if (!searchedQuery.trim() && !filterActive)
      return `선수 이름을 입력하세요. (총 ${meta.players.length.toLocaleString()}명)`
    if (!results.length) return '검색 결과가 없습니다.'
    if (groups.length === 1) return `카드 ${results.length}장`
    return `선수 ${groups.length}명, 카드 ${results.length}장`
  })

  function showResults(cards: Player[]) {
    results = cards
    expanded.clear()
    // 한 명만 나오면 바로 펼친다
    const players = new Set(cards.map((c) => pidOf(c.id)))
    if (players.size === 1) expanded.add(pidOf(cards[0].id))
  }

  function runSearch() {
    pidLabel = null
    searchedQuery = query
    showResults(searchCards(query, filter))
  }

  function onFilterChange(next: Filter) {
    filter = next
    runSearch()
  }

  function closeFilter() {
    filterOpen = false
    // 시즌 이름으로 고른 시즌은 필터 창 안에서만 쓰는 임시 선택 (기존 동작 유지)
    if (filter.seasonIds.length) onFilterChange({ ...filter, seasonIds: [] })
  }

  function toggle(pid: number) {
    if (expanded.has(pid)) expanded.delete(pid)
    else expanded.add(pid)
  }

  /** 이미지 파일명에서 찾은 선수를 목록에 띄우고, spid가 있으면 그 카드를 선택 */
  export async function showPlayer(pid: number, spid: number | null) {
    query = ''
    searchedQuery = ''
    pidLabel = pid
    showResults(cardsOfPid(pid))
    const card = spid !== null ? results.find((c) => c.id === spid) : undefined
    if (!card) return
    onSelect(card)
    await tick()
    list?.querySelector(`[data-spid="${spid}"]`)?.scrollIntoView({ block: 'center' })
  }
</script>

<SearchPanel
  bind:query
  bind:list
  placeholder="선수 이름 검색"
  disabled={!meta.loaded}
  loading={!meta.loaded && !meta.error}
  {status}
  onSearch={runSearch}
>
  {#snippet tools()}
    <button
      type="button"
      class="btn"
      class:filtered={filterActive}
      data-filter-toggle
      aria-expanded={filterOpen}
      disabled={!meta.loaded}
      onclick={() => (filterOpen ? closeFilter() : (filterOpen = true))}
    >
      <SlidersHorizontal size={15} /> 필터
    </button>
    {#if filterOpen}
      <SeasonFilter {filter} onChange={onFilterChange} onClose={closeFilter} />
    {/if}
  {/snippet}

  {#each groups as group (group.pid)}
    <CardGroup
      {group}
      expanded={expanded.has(group.pid)}
      {selectedSpid}
      onToggle={() => toggle(group.pid)}
      {onSelect}
    />
  {/each}
</SearchPanel>

<style>
  .btn.filtered {
    border-color: var(--gold);
    color: var(--gold);
    background: var(--gold-soft);
  }
</style>
