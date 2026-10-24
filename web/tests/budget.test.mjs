import test from 'node:test';
import assert from 'node:assert/strict';
import { parseBudget, fitsBudget } from '../src/lib/budget.ts';
import { options } from '../src/lib/fixtures.ts';

test('chat recognizes explicit rupee budgets and stores integer paise', () => {
  for (const input of ['a 500rupees package', 'a package under ₹500', 'Rs. 500', 'INR 500', '500 rupees for 2 people']) {
    assert.equal(parseBudget(input), 50_000, input);
  }
  assert.equal(parseBudget('500'), null);
  assert.equal(parseBudget('500', true), 50_000);
  assert.equal(parseBudget('₹1'), 100);
  assert.equal(parseBudget('₹10,00,000'), 100_000_000);
  assert.equal(parseBudget('₹1,800'), 180_000);
});

test('invalid or ambiguous budgets require clarification', () => {
  for (const input of ['', '0', '-500', '500.5', 'Infinity', '1e3', '500k', '1000001', '50,00', '₹-500', '₹0', '₹500.50', '₹500 or ₹800', '₹500 per person', '₹500 each', '₹500-700', '₹500 to 700', 'between ₹500 and 700', '1e3 rupees', '₹1e3', '2.5k rupees', '₹500k']) {
    assert.equal(parseBudget(input, true), null, input);
  }
  assert.equal(parseBudget('for 2 people at 7 tonight'), null);
});

test('₹500 cannot return any of the existing more expensive samples', () => {
  assert.deepEqual(options.filter(item => fitsBudget(item, parseBudget('500rupees'))), []);
});

test('budget boundaries are inclusive and unavailable samples stay excluded', () => {
  assert.deepEqual(options.filter(item => fitsBudget(item, 180_000)).map(item => item.id), ['waterfront']);
  assert.deepEqual(options.filter(item => fitsBudget(item, 240_000)).map(item => item.id), ['waterfront', 'clay']);
  assert.deepEqual(options.filter(item => fitsBudget(item, 320_000)).map(item => item.id), ['waterfront', 'clay']);
  assert.equal(fitsBudget(options[0], 179_999), false);
  assert.equal(fitsBudget(options[0], undefined), false);
  assert.equal(fitsBudget(options[0], NaN), false);
  assert.equal(fitsBudget(options[0], Infinity), false);
  assert.equal(fitsBudget({ pricePaise: -1, availability: 'AVAILABLE' }, 100), false);
  assert.equal(fitsBudget({ pricePaise: 99.5, availability: 'AVAILABLE' }, 100), false);
});
