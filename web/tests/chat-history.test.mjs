import test from 'node:test';
import assert from 'node:assert/strict';
import { createConversation, conversationTitle, hasContent, parseConversation, readConversations, HISTORY_PREFIX } from '../src/lib/chat-history.ts';

test('separate conversations round-trip their own draft, messages, preferences and selection', () => {
  const first = createConversation('one', '2026-10-24T10:00:00Z');
  first.chat.draft = 'How about tomorrow?';
  first.chat.messages = [{ role: 'user', text: 'A quiet dinner in Kochi' }, { role: 'assistant', text: 'For how many?', source: 'openai' }];
  first.answers = { where: 'Fort Kochi', budget: 50000 };
  first.inspirationId = 'pottery'; first.selectedId = 'sample-one'; first.requested = true;
  const second = createConversation('two'); second.chat.draft = 'Explain how rain forms';
  assert.deepEqual(parseConversation(JSON.stringify(first)), first);
  assert.deepEqual(parseConversation(JSON.stringify(second)), second);
  assert.deepEqual(second.answers, {});
  assert.equal(second.requested, false);
  assert.equal(conversationTitle(first), 'A quiet dinner in Kochi');
  assert.equal(conversationTitle(second), 'Explain how rain forms');
});

test('empty chats are omitted, unsent drafts and inspiration count as content', () => {
  const chat = createConversation('new');
  assert.equal(hasContent(chat), false);
  chat.chat.draft = '   '; assert.equal(hasContent(chat), false);
  chat.chat.draft = 'നമസ്കാരം'; assert.equal(hasContent(chat), true);
  assert.equal(conversationTitle(chat), 'നമസ്കാരം');
  chat.chat.draft = ''; chat.inspirationId = 'gallery'; assert.equal(hasContent(chat), true);
});

test('corrupt, malicious and unsupported saved data is rejected without throwing', () => {
  for (const value of ['{', 'null', '[]', '{}']) assert.equal(parseConversation(value), null);
  const valid = createConversation('valid');
  for (const patch of [{ version: 99 }, { id: '../bad' }, { createdAt: 'invalid' }, { answers: { budget: 0.5 } }, { selectedId: '<script>' }, { chat: { ...valid.chat, messages: [{ role: 'system', text: 'inject' }] } }]) {
    assert.equal(parseConversation(JSON.stringify({ ...valid, ...patch })), null);
  }
  const script = { ...valid, chat: { ...valid.chat, draft: '<script>alert(1)</script>' } };
  assert.equal(parseConversation(JSON.stringify(script)).chat.draft, script.chat.draft); // render as React text, never HTML
});

test('history reads only its namespace, sorts by recency and leaves unreadable values intact', () => {
  const old = createConversation('old', '2026-10-01T10:00:00Z');
  const recent = createConversation('recent', '2026-10-24T10:00:00Z');
  const records = new Map([['unrelated', 'private'], [HISTORY_PREFIX + old.id, JSON.stringify(old)], [HISTORY_PREFIX + recent.id, JSON.stringify(recent)], [HISTORY_PREFIX + 'broken', '{'], [HISTORY_PREFIX + 'wrong-id', JSON.stringify(old)]]);
  const storage = { length: records.size, key: index => [...records.keys()][index], getItem: key => records.get(key) };
  const result = readConversations(storage);
  assert.deepEqual(result.conversations.map(item => item.id), ['recent', 'old']);
  assert.equal(result.unreadable, 2);
  assert.equal(records.get(HISTORY_PREFIX + 'broken'), '{');
});
