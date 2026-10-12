<script lang="ts">
  import { seasonIdOf, seasonOf } from '../meta.svelte'

  interface Props {
    spid: number
    /** 시즌 이름 뒤에 붙일 글자 (연도 접미사 등) */
    suffix?: string
    size?: 'small' | 'regular'
  }

  let { spid, suffix = '', size = 'small' }: Props = $props()

  const season = $derived(seasonOf(spid))
</script>

<span class="badge {size}" title={season?.className}>
  {#if season?.seasonImg}<img src={season.seasonImg} alt="" />{/if}
  {season?.shortName ?? `시즌 ${seasonIdOf(spid)}`}{suffix}
</span>

<style>
  .badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    min-width: 0;
    color: var(--text-2);
    font-weight: 600;
    white-space: nowrap;
  }

  .small {
    font-size: var(--text-xs);
  }

  .small img {
    height: 16px;
  }

  .regular {
    font-size: var(--text-sm);
  }

  .regular img {
    height: 18px;
  }

  img {
    width: auto;
    flex: none;
  }
</style>
