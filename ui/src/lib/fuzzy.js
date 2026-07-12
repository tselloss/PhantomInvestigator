export function fuzzyMatch(query, text) {
  const q = query.trim().toLowerCase();
  const t = text.toLowerCase();
  if (!q) return 0;

  const idx = t.indexOf(q);
  if (idx !== -1) return 1000 - idx;

  let qi = 0;
  let score = 0;
  let lastMatch = -1;
  for (let ti = 0; ti < t.length && qi < q.length; ti++) {
    if (t[ti] === q[qi]) {
      score += lastMatch === ti - 1 ? 3 : 1;
      lastMatch = ti;
      qi++;
    }
  }
  return qi === q.length ? score : null;
}
