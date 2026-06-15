export type CyberEventDetail = {
  'cyber:npc:interact':       { npcId: string; npcName: string };
  'cyber:object:interact':    { objectId: string; contextHint?: string };
  'cyber:door:approach':      { targetScene: string; roomName: string; modeDescription: string };
  'cyber:scene:changed':      { sceneKey: string; roomName: string };
  'cyber:notification:badge': { count: number };
  'cyber:panel:opened':       { panelId: string };
  'cyber:panel:closed':       { panelId: string };
  'cyber:door:confirmed':     { targetScene: string };
  'cyber:door:cancelled':     Record<string, never>;
  'cyber:review:done':        { processedCount: number };
};

export function dispatch<K extends keyof CyberEventDetail>(
  name: K,
  detail: CyberEventDetail[K],
): void {
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

export function listen<K extends keyof CyberEventDetail>(
  name: K,
  handler: (detail: CyberEventDetail[K]) => void,
): () => void {
  const fn = (e: Event) => handler((e as CustomEvent<CyberEventDetail[K]>).detail);
  window.addEventListener(name, fn);
  return () => window.removeEventListener(name, fn);
}
