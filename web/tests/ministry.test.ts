import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { strand } from '../src/features/blog/ministry/strands.ts';

// The twenty-sixth post's figures, as the page reads them (apps/blog/posts/ministry).
const dir = new URL('../../back/apps/blog/posts/ministry/', import.meta.url);
const figures = JSON.parse(readFileSync(new URL('figures.json', dir), 'utf8'));
const meta = readFileSync(new URL('meta.yaml', dir), 'utf8');

test('the title\'s count is the names counted, and the longest is the 2017 ministry', () => {
  assert.ok(meta.includes(`${figures.names.length} اسما`));
  assert.equal(figures.longest, 'التربية الوطنية والتكوين المهني والتعليم العالي والبحث العلمي');
  const longest = figures.names.find((n: { name: string }) => n.name === figures.longest);
  assert.deepEqual([longest.from, longest.to], [2017, 2021]);
  for (const n of figures.names) assert.ok(n.texts >= 3 && n.from <= n.to);
});

test('a name\'s strand: the schools, higher education, or both', () => {
  assert.equal(strand('التربية الوطنية'), 'school');
  assert.equal(strand('التعليم العالي والبحث العلمي والابتكار'), 'higher');
  assert.equal(strand('التربية الوطنية والتعليم العالي وتكوين الأطر والبحث العلمي'), 'both');
  assert.equal(strand('التعليم الابتدائي'), 'school');
});
