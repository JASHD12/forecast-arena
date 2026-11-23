// Ask the Arena, tier 2 (T316): an optional model that runs in the visitor's browser and may only
// reword the facts of a lookup or document answer. Nothing is downloaded until the visitor clicks
// the button; chat.ts rejects any wording with a number that is not in the facts. Source of
// src/arena/site/static/chat-llm.js: edit this file and run `make site-ts`.
(function (): void {
  'use strict';

  // Pinned third-party code and model (owner approval H41; see docs/SOURCES.md, checked 2026-11-23).
  const LIB_URL = 'https://cdn.jsdelivr.net/npm/@mlc-ai/web-llm@0.2.87/lib/index.js';
  const LIB_SHA256 = '3bff4c55cd2f0200711517341babcebe7a91a8ef85b983420439fcf26835a674';
  const MODEL_ID = 'Qwen2.5-0.5B-Instruct-q4f16_1-MLC';

  interface Message { role: 'system' | 'user'; content: string }
  interface Engine {
    chat: { completions: { create(req: {
      messages: Message[]; temperature: number; max_tokens: number;
    }): Promise<{ choices: Array<{ message: { content: string | null } }> }> } };
  }
  interface WebLLM {
    CreateMLCEngine(id: string, cfg: { initProgressCallback: (p: { text: string }) => void }): Promise<Engine>;
  }

  function buildMessages(facts: string): Message[] {
    return [
      {
        role: 'system',
        content: 'Reword the facts the user gives you as at most two short, plain sentences. ' +
          'Use only those facts. Do not add numbers, reasons, advice or predictions.',
      },
      { role: 'user', content: facts.slice(0, 1500) },
    ];
  }

  function createRephraser(engine: Engine): (facts: string) => Promise<string | null> {
    return async (facts: string): Promise<string | null> => {
      const r = await engine.chat.completions.create({
        messages: buildMessages(facts), temperature: 0, max_tokens: 120,
      });
      const out = r.choices[0] && r.choices[0].message.content;
      return out ? out.trim() : null;
    };
  }

  async function sha256Hex(text: string): Promise<string> {
    const bytes = new TextEncoder().encode(text);
    const digest = await crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, '0')).join('');
  }

  async function loadLibrary(): Promise<WebLLM> {
    const res = await fetch(LIB_URL);
    if (!res.ok) throw new Error('library download failed');
    const text = await res.text();
    if ((await sha256Hex(text)) !== LIB_SHA256) throw new Error('library hash mismatch, not loaded');
    const url = URL.createObjectURL(new Blob([text], { type: 'text/javascript' }));
    const mod: unknown = await import(url);
    URL.revokeObjectURL(url);
    return mod as WebLLM;
  }

  const api = { buildMessages, createRephraser, MODEL_ID, LIB_SHA256 };
  // `module` is declared in chat.ts (one global scope); it exists only under Node.
  if (typeof module !== 'undefined' && module && typeof document === 'undefined') {
    module.exports = api;
    return;
  }
  if (typeof document === 'undefined') return;

  const box = document.getElementById('ask-llm');
  const button = document.getElementById('ask-llm-load') as HTMLButtonElement | null;
  const status = document.getElementById('ask-llm-status');
  if (!box || !button || !status) return;
  const gpu = (navigator as unknown as { gpu?: { requestAdapter(): Promise<unknown> } }).gpu;
  if (!gpu) return; // the box stays hidden: this browser cannot run the model
  gpu.requestAdapter().then((adapter) => { if (adapter) box.hidden = false; }).catch(() => undefined);
  button.addEventListener('click', () => {
    button.disabled = true;
    status.textContent = 'Downloading the library and the model (about 290 MB)...';
    loadLibrary()
      .then((lib) => lib.CreateMLCEngine(MODEL_ID, {
        initProgressCallback: (p) => { status.textContent = p.text; },
      }))
      .then((engine) => {
        const chat = (window as unknown as { ArenaChat?: { setRephraser: (r: ((f: string) => Promise<string | null>) | null) => void } }).ArenaChat;
        if (!chat) throw new Error('chat not ready');
        chat.setRephraser(createRephraser(engine));
        status.textContent = 'Model ready. Lookup and document answers are now also reworded on your device.';
      })
      .catch((e: Error) => {
        status.textContent = 'The in-browser model could not be loaded (' + e.message + '). The chat works as before.';
        button.disabled = false;
      });
  });
})();
