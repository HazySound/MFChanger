<script lang="ts">
  import type { Snippet } from 'svelte'
  import SeasonBadge from '../../lib/components/SeasonBadge.svelte'
  import SelectionHeader from '../../lib/components/SelectionHeader.svelte'
  import type { Player } from '../../lib/types'

  interface Props {
    card: Player
    changedAt: string | null
    actions?: Snippet
  }

  let { card, changedAt, actions }: Props = $props()
</script>

<SelectionHeader title={card.name} {changedAt} {actions}>
  {#snippet facts()}
    <SeasonBadge spid={card.id} size="regular" />
    <span class="faint spid">SPID p{card.id}</span>
  {/snippet}
</SelectionHeader>

<style>
  .spid {
    user-select: text;
  }
</style>
