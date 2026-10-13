// DeepSeek as the assistant's model: the loop in logic.mjs speaks the Anthropic message shape, so this adapter turns one
// request into DeepSeek's chat-completions form and the reply back. Pure except deepseekCreate (fetch); tested with Node.
// What DeepSeek can't do here: look at photos (they become a note) and the hosted web search (dropped).
export const DS_URL = 'https://api.deepseek.com/chat/completions';
export const DS_MODEL = 'deepseek-chat';

const textOfBlocks = c => typeof c === 'string' ? c : (Array.isArray(c) ? c.filter(b => b && b.type === 'text').map(b => b.text).join('\n') : '');

export function toDeepSeek(body) {
  const messages = [];
  const sys = textOfBlocks(body.system);
  if (sys) messages.push({ role: 'system', content: sys });
  for (const m of body.messages || []) {
    if (typeof m.content === 'string') { messages.push({ role: m.role, content: m.content }); continue; }
    const blocks = Array.isArray(m.content) ? m.content : [];
    if (m.role === 'assistant') {
      const text = blocks.filter(b => b.type === 'text').map(b => b.text).join('\n');
      const calls = blocks.filter(b => b.type === 'tool_use')
        .map(b => ({ id: String(b.id), type: 'function', function: { name: String(b.name), arguments: JSON.stringify(b.input || {}) } }));
      const msg = { role: 'assistant', content: text || (calls.length ? '' : '…') };
      if (calls.length) msg.tool_calls = calls;
      messages.push(msg);
    } else {
      for (const b of blocks) if (b.type === 'tool_result')            // tool answers go first, right after the call
        messages.push({ role: 'tool', tool_call_id: String(b.tool_use_id), content: (b.is_error ? 'Ошибка: ' : '') + textOfBlocks(b.content) });
      const imgs = blocks.filter(b => b.type === 'image').length;
      const text = blocks.filter(b => b.type === 'text').map(b => b.text).join('\n');
      const note = imgs ? '[Человек приложил фото, но эта модель не видит изображений — попроси описать словами, что на фото.]\n' : '';
      if (text || note) messages.push({ role: 'user', content: note + text });
    }
  }
  const tools = (body.tools || []).filter(t => t && t.input_schema && t.name)
    .map(t => ({ type: 'function', function: { name: t.name, description: t.description || '', parameters: t.input_schema } }));
  const out = { model: DS_MODEL, messages, max_tokens: Math.min(+body.max_tokens || 2000, 8000), temperature: 0.4 };
  if (tools.length) out.tools = tools;
  return out;
}

export function fromDeepSeek(r) {
  const ch = (r && r.choices && r.choices[0]) || {}, msg = ch.message || {};
  const content = [];
  if (msg.content && String(msg.content).trim()) content.push({ type: 'text', text: String(msg.content) });
  for (const c of msg.tool_calls || []) {
    let input = {};
    try { input = JSON.parse((c.function && c.function.arguments) || '{}') || {}; } catch (e) { input = {}; }
    content.push({ type: 'tool_use', id: String(c.id), name: String(c.function && c.function.name), input });
  }
  const fr = ch.finish_reason;
  const stop_reason = fr === 'tool_calls' || (msg.tool_calls && msg.tool_calls.length) ? 'tool_use' : fr === 'length' ? 'max_tokens' : 'end_turn';
  const u = (r && r.usage) || {};
  return { stop_reason, content, usage: { input_tokens: +u.prompt_tokens || 0, output_tokens: +u.completion_tokens || 0,
    cache_read_input_tokens: +u.prompt_cache_hit_tokens || 0 } };
}

/* one call; errors carry .status like the Anthropic SDK's, never the key */
export async function deepseekCreate(body, key, ms = 40000) {
  const ctl = new AbortController(), t = setTimeout(() => ctl.abort(), ms);
  try {
    const res = await fetch(DS_URL, { method: 'POST', signal: ctl.signal,
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + key }, body: JSON.stringify(toDeepSeek(body)) });
    const j = await res.json().catch(() => null);
    if (!res.ok) throw Object.assign(new Error((j && j.error && j.error.message) || 'HTTP ' + res.status), { status: res.status });
    return fromDeepSeek(j);
  } catch (e) {
    if (e && e.name === 'AbortError') throw Object.assign(new Error('timeout'), { status: 0 });
    throw e;
  } finally { clearTimeout(t); }
}
