import test from 'node:test';
import assert from 'node:assert/strict';
import { appendStarter, isFollowUpQuestion } from '../src/lib/chat-input.ts';
import { chatStarters } from '../src/lib/fixtures.ts';
import { questions, isComplete } from '../src/lib/questions.ts';

test('all three starters can fill a draft, including the anniversary idea', () => {
  assert.equal(chatStarters.length, 3);
  assert.equal(chatStarters[2].text, 'I forgot today was the anniversary');
  for (const { text } of chatStarters) assert.equal(appendStarter('', text, 1000), text);
});

test('adding inspiration preserves existing draft text and respects the input limit', () => {
  assert.equal(appendStarter('Budget ₹500.', 'A relaxed date', 1000), 'Budget ₹500. A relaxed date');
  assert.equal(appendStarter('My idea\n', 'More detail', 1000), 'My idea\nMore detail');
  assert.equal(appendStarter('abc', 'd', 5), 'abc d');
  assert.equal(appendStarter('abc', 'de', 5), null);
});

test('all planning prompts accept text rather than fixed choices', () => {
  for (const question of questions) {
    assert.equal(question.type, question.id === 'budget' ? 'budget' : 'text');
    assert.equal(question.choices, undefined);
    assert.ok(question.placeholder);
  }
});

test('custom dates, locations and preferences are not limited to canned answers', () => {
  const answers = {
    when: 'Next Saturday at 8:30 pm, until about 10',
    where: 'Near my office in Vyttila',
    who: 'Me and three friends',
    occasion: 'Our first evening off in weeks',
    budget: 50000,
    kind: 'A quiet outdoor activity, then a small snack',
    constraints: 'Step-free access and no alcohol',
    transport: 'We can walk for about ten minutes',
  };
  assert.equal(isComplete(answers), true);
  for (const [field, value] of Object.entries(answers)) {
    if (field !== 'budget') assert.equal(isFollowUpQuestion(value), false, field);
  }
});

test('preview recognizes questions that must not be saved as preferences', () => {
  for (const input of ['What is gravity?', 'Why do you need my budget', 'Explain photosynthesis', 'Can you answer something else?', 'Who invented the telescope', 'Are you a real AI?']) {
    assert.equal(isFollowUpQuestion(input), true, input);
  }
});
