// k6 scenario: each iteration = one full trip conversation (new thread → ask → approve).
// Run via bench/run_load.py (fixed VUs for a fixed duration, one run per VU level).
import http from 'k6/http';
import { check } from 'k6';

const BASE = __ENV.BASE_URL || 'http://host.docker.internal:8000';
const ASK = 'Plan a trip from Delhi to Goa, 2026-12-18, 4 days, 2 people, budget ₹60000. We like beaches.';

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '30s',
  thresholds: { http_req_failed: ['rate<0.01'] },
};

export default function () {
  const h = { headers: { 'Content-Type': 'application/json', 'X-User': `load-${__VU}` } };
  const t = http.post(`${BASE}/threads`, null, { tags: { name: 'threads' } }).json().thread_id;
  const r1 = http.post(`${BASE}/threads/${t}/messages`, JSON.stringify({ content: ASK }), { ...h, tags: { name: 'plan' } });
  check(r1, { 'plan → awaiting_approval': (r) => r.status === 200 && r.json().status === 'awaiting_approval' });
  const r2 = http.post(`${BASE}/threads/${t}/approve`, JSON.stringify({ decision: 'approve' }), { ...h, tags: { name: 'approve' } });
  check(r2, { 'approve → done': (r) => r.status === 200 && r.json().status === 'done' });
}
