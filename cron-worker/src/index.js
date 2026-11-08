// 예약 시간이 되면 스튜디오의 tick 주소를 불러요. 실제로 무엇을 올릴지는 GitHub 쪽 일정표가 정해서, 여러 번 불려도 같은 글이 두 번 올라가지 않아요.
export default {
  async scheduled(event, env, ctx) {
    const what = event.cron === "6 11 * * *" ? "generate" : "publish";
    const r = await fetch(`${env.STUDIO_TICK}?what=${what}`, { headers: { "user-agent": "studio-alarm" } });
    console.log(`알람 ${event.cron} → ${what}: ${r.status} ${await r.text()}`);
  },
  async fetch() {
    // 주소로 들어와도 아무것도 실행하지 않아요 (살아 있는지 확인용)
    return new Response("studio-alarm 정상 (예약: 07:01, 12:01, 12:31, 20:01, 20:06, 21:01 한국 시간)\n", { headers: { "content-type": "text/plain; charset=utf-8" } });
  },
};
