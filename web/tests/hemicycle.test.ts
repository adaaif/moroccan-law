import { test } from 'node:test';
import assert from 'node:assert/strict';
import { hemicycle } from '../src/topics/kit/changes/hemicycle.ts';

// The Chamber of Representatives' 395 seats (organic law 27.11, art. 1) and a committee's 44.
for (const total of [395, 120, 44, 9]) {
  test(`a hemicycle of ${total} seats draws each seat once, inside the picture, none on another`, () => {
    const { seats, r, height } = hemicycle(total);
    assert.equal(seats.length, total);
    for (const s of seats) assert.ok(s.x - r >= 0 && s.x + r <= 360 && s.y - r >= 0 && s.y + r <= height, `seat at ${s.x}, ${s.y}`);
    let nearest = Infinity;
    for (let i = 0; i < seats.length; i += 1) for (let j = i + 1; j < seats.length; j += 1) {
      nearest = Math.min(nearest, Math.hypot(seats[i].x - seats[j].x, seats[i].y - seats[j].y));
    }
    assert.ok(nearest > 2 * r, `two seats ${nearest.toFixed(2)} apart for a radius of ${r.toFixed(2)}`);
  });
}

// The same seats as a horseshoe arch: the rows' ends carried below the diameter, the floor wider for the count.
for (const total of [395, 120]) {
  test(`a horseshoe of ${total} seats draws each seat once, inside the picture, none on another, its feet turned in`, () => {
    const { seats, r, height, cx, cy, inner } = hemicycle(total, 360, 0.5, 0.56);
    assert.equal(seats.length, total);
    for (const s of seats) assert.ok(s.x - r >= 0 && s.x + r <= 360 && s.y - r >= 0 && s.y + r <= height, `seat at ${s.x}, ${s.y}`);
    let nearest = Infinity;
    for (let i = 0; i < seats.length; i += 1) for (let j = i + 1; j < seats.length; j += 1) {
      nearest = Math.min(nearest, Math.hypot(seats[i].x - seats[j].x, seats[i].y - seats[j].y));
    }
    assert.ok(nearest > 2 * r, `two seats ${nearest.toFixed(2)} apart for a radius of ${r.toFixed(2)}`);
    // The first seat and the last stand under the centre, nearer the middle than the arch's widest point.
    assert.ok(seats[0].y > cy && seats[total - 1].y > cy);
    assert.ok(seats[0].x > Math.min(...seats.map((s) => s.x)) && seats[0].x < cx);
    // The floor stays clear for the count.
    assert.ok(seats.every((s) => Math.hypot(s.x - cx, s.y - cy) >= inner - 0.01));
    for (let i = 1; i < seats.length; i += 1) assert.ok(seats[i].angle <= seats[i - 1].angle);
  });
}

test('the seats come in the order a sweep from the left meets them: a count fills a wedge, never scattered dots', () => {
  const { seats } = hemicycle(395);
  for (let i = 1; i < seats.length; i += 1) assert.ok(seats[i].angle <= seats[i - 1].angle);
  // The 179 who voted for are all to the left of the 90 seats that did not vote.
  assert.ok(Math.max(...seats.slice(0, 179).map((s) => s.x)) < Math.max(...seats.slice(305).map((s) => s.x)));
  assert.ok(seats.slice(0, 179).every((s) => s.angle > seats[304].angle));
});
