<script lang="ts">
  import { ChevronRight, X } from '@lucide/svelte'
  import { untrack } from 'svelte'
  import { SvelteSet } from 'svelte/reactivity'
  import { scale, slide } from 'svelte/transition'
  import { ALL_YEARS, CATEGORY_ORDER, meta, NO_YEAR, type SeasonFilter } from '../../lib/meta.svelte'

  interface Props {
    filter: SeasonFilter
    onChange: (filter: SeasonFilter) => void
    onClose: () => void
  }

  let { filter, onChange, onClose }: Props = $props()

  const SEASON_RESULT_LIMIT = 24

  // 처음 열 때 선택된 카테고리는 펼쳐 둔다
  const expanded = new SvelteSet(untrack(() => Object.keys(filter.categories)))
  let seasonQuery = $state('')
  let root = $state<HTMLElement>()

  const categories = $derived(CATEGORY_ORDER.filter((cat) => meta.seasons.some((s) => s.category === cat)))

  const seasonMatches = $derived.by(() => {
    const q = seasonQuery.trim().toLowerCase()
    if (!q) return []
    return meta.seasons.filter((s) => s.shortName.toLowerCase().includes(q) || s.className.toLowerCase().includes(q))
  })

  function yearOptions(category: string): string[] {
    const inCategory = meta.seasons.filter((s) => s.category === category)
    const years = [...new Set(inCategory.map((s) => s.year).filter(Boolean))].sort().reverse()
    return [ALL_YEARS, ...years, ...(inCategory.some((s) => !s.year) ? [NO_YEAR] : [])]
  }

  const yearLabel = (year: string) => (/^\d{2}$/.test(year) ? `'${year}` : year)

  function toggleExpand(category: string) {
    if (expanded.has(category)) expanded.delete(category)
    else expanded.add(category)
  }

  function toggleYear(category: string, year: string) {
    const current = filter.categories[category] ?? []
    let next: string[]
    if (year === ALL_YEARS) next = current.includes(ALL_YEARS) ? [] : [ALL_YEARS]
    else if (current.includes(year)) next = current.filter((y) => y !== year)
    else next = [...current.filter((y) => y !== ALL_YEARS), year]

    const categoriesNext = { ...filter.categories }
    if (next.length) categoriesNext[category] = next
    else delete categoriesNext[category]
    onChange({ ...filter, categories: categoriesNext })
  }

  function clearCategory(category: string) {
    const { [category]: _removed, ...rest } = filter.categories
    onChange({ ...filter, categories: rest })
  }

  function toggleSeason(seasonId: number) {
    const ids = filter.seasonIds.includes(seasonId)
      ? filter.seasonIds.filter((id) => id !== seasonId)
      : [...filter.seasonIds, seasonId]
    onChange({ ...filter, seasonIds: ids })
  }

  function onSeasonQuery(value: string) {
    seasonQuery = value
    // 시즌 이름 검색을 지우면 그 검색으로 고른 시즌도 함께 해제
    if (!value.trim() && filter.seasonIds.length) onChange({ ...filter, seasonIds: [] })
  }

  function reset() {
    seasonQuery = ''
    expanded.clear()
    onChange({ categories: {}, seasonIds: [] })
  }

  function onPointerDown(event: PointerEvent) {
    const target = event.target as Element
    // 필터 버튼 클릭은 버튼 자신이 열기/닫기를 처리
    if (root && !root.contains(target) && !target.closest('[data-filter-toggle]')) onClose()
  }
</script>

<svelte:window onpointerdown={onPointerDown} onkeydown={(e) => e.key === 'Escape' && onClose()} />

<div
  class="popover"
  bind:this={root}
  role="dialog"
  aria-label="시즌 필터"
  transition:scale={{ start: 0.97, duration: 140 }}
>
  <div class="head">
    <h2>시즌 필터</h2>
    <button type="button" class="btn ghost small" onclick={reset}>전체 초기화</button>
  </div>

  <input
    class="field"
    placeholder="시즌 이름 검색 (예: GR, TOTS)"
    value={seasonQuery}
    oninput={(e) => onSeasonQuery(e.currentTarget.value)}
  />

  <div class="body">
    {#if seasonQuery.trim()}
      {#if seasonMatches.length}
        <div class="chips">
          {#each seasonMatches.slice(0, SEASON_RESULT_LIMIT) as season (season.seasonId)}
            <button
              type="button"
              class="chip"
              class:on={filter.seasonIds.includes(season.seasonId)}
              title={season.className}
              onclick={() => toggleSeason(season.seasonId)}
            >
              {#if season.seasonImg}<img src={season.seasonImg} alt="" />{/if}
              {season.shortName}
            </button>
          {/each}
        </div>
        {#if seasonMatches.length > SEASON_RESULT_LIMIT}
          <p class="faint more">
            그 밖에 {seasonMatches.length - SEASON_RESULT_LIMIT}개 시즌이 더 있습니다. 검색어를 더 구체적으로
            입력해주세요.
          </p>
        {/if}
      {:else}
        <p class="faint more">일치하는 시즌이 없습니다.</p>
      {/if}
    {:else}
      {#each categories as category (category)}
        {@const selected = filter.categories[category] ?? []}
        <div class="category">
          <div class="category-head">
            <button
              type="button"
              class="expand"
              aria-expanded={expanded.has(category)}
              onclick={() => toggleExpand(category)}
            >
              <span class="chevron" class:open={expanded.has(category)}><ChevronRight size={14} /></span>
              {category}
            </button>
            {#if selected.length}
              <button type="button" class="count" onclick={() => clearCategory(category)}>
                {selected.includes(ALL_YEARS) ? '전체' : `${selected.length}개`}
                <X size={12} />
              </button>
            {/if}
          </div>
          {#if expanded.has(category)}
            <div class="chips years" transition:slide={{ duration: 160 }}>
              {#each yearOptions(category) as year (year)}
                <button
                  type="button"
                  class="chip"
                  class:on={selected.includes(year)}
                  onclick={() => toggleYear(category, year)}
                >
                  {yearLabel(year)}
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    {/if}
  </div>
</div>

<style>
  .popover {
    /* 검색 패널(SearchPanel) 너비에 맞춰 검색창 바로 아래에 연다 */
    position: absolute;
    top: 58px;
    left: 10px;
    right: 10px;
    z-index: 20;
    display: grid;
    gap: 10px;
    padding: 14px;
    border-radius: var(--radius-panel);
    background: var(--surface);
    border: 1px solid var(--line-strong);
    box-shadow: var(--shadow-pop);
    transform-origin: top center;
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h2 {
    font-size: var(--text-md);
  }

  .body {
    display: grid;
    gap: 4px;
    max-height: 300px;
    overflow-y: auto;
    margin-right: -6px;
    padding-right: 6px;
  }

  .category-head {
    display: flex;
    align-items: center;
    border-radius: var(--radius-control);
  }

  .category-head:hover {
    background: var(--surface-2);
  }

  .expand {
    display: flex;
    flex: 1;
    align-items: center;
    gap: 6px;
    height: 34px;
    padding: 0 8px;
    border: 0;
    background: none;
    font-weight: 700;
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
  }

  .chevron {
    display: inline-flex;
    color: var(--text-3);
    transition: transform 0.18s var(--ease-out);
  }

  .chevron.open {
    transform: rotate(90deg);
  }

  .count {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-right: 6px;
    padding: 2px 8px;
    border: 0;
    border-radius: 999px;
    background: var(--gold);
    color: var(--gold-ink);
    font-size: var(--text-xs);
    font-weight: 700;
    cursor: pointer;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .years {
    padding: 4px 8px 10px 28px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    height: 28px;
    padding: 0 10px;
    border: 1px solid var(--line-strong);
    border-radius: 999px;
    background: transparent;
    color: var(--text-2);
    font-size: var(--text-xs);
    font-weight: 600;
    cursor: pointer;
    transition:
      background 0.15s,
      border-color 0.15s,
      color 0.15s;
  }

  .chip:hover {
    color: var(--text);
    border-color: var(--text-3);
  }

  .chip.on {
    background: var(--gold-soft);
    border-color: var(--gold);
    color: var(--gold);
  }

  .chip img {
    height: 16px;
    width: auto;
  }

  .more {
    padding: 6px 2px;
  }
</style>
