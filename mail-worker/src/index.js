// 관리자 메일 거르개 (Cloudflare Email Worker)
// 1) 메일 제목과 본문을 읽어요  2) 욕설, 비하, 협박 표현이 있으면 버려요  3) 나머지는 사장님 Gmail로 넘겨요
import PostalMime from "postal-mime";

// 띄어쓰기, 특수문자, 숫자를 빼고 비교해요 (시 1 발, 씨.발 같은 우회도 잡게)
const WORDS = [
  "시발", "씨발", "씨빨", "씨바", "시바", "쉬발", "ㅅㅂ", "ㅆㅂ", "ㅅ발", "십새", "씹",
  "개새끼", "개새기", "개색", "개색기", "개세끼", "ㄱㅅㄲ", "새끼야", "새끼들",
  "병신", "븅신", "빙신", "ㅂㅅ", "등신", "좆", "ㅈ같", "존나", "졸라", "ㅈㄴ",
  "미친놈", "미친년", "미친새", "또라이", "지랄", "ㅈㄹ", "닥쳐", "엿먹",
  "죽여버", "뒤져라", "꺼져라", "뒈져", "디져라", "한남충", "김치녀", "된장녀", "틀딱", "급식충", "맘충", "홍어", "쪽바리", "짱깨",
  "느금", "니애미", "니미", "엠창",
  "fuck", "shit", "bitch", "asshole",
];
// 그냥 쓰는 말에도 들어가는 짧은 표현은 예외 (예: 시바견, 씹다)
const ALLOW = ["시바견", "시바이누", "씹다", "씹어", "씹는", "곱씹", "홍어회", "홍어삼합"];

function clean(s) {
  return (s || "").toLowerCase().replace(/[\s0-9.,!?~\-_*·:;'"`^()[\]{}<>/\\|+=@#$%&]/g, "");
}

function badWords(text) {
  let t = clean(text);
  for (const a of ALLOW) t = t.split(clean(a)).join("");
  return WORDS.filter((w) => t.includes(clean(w)));
}

export default {
  async email(message, env, ctx) {
    let subject = message.headers.get("subject") || "";
    let body = "";
    try {
      const mail = await PostalMime.parse(message.raw);
      subject = mail.subject || subject;
      body = (mail.text || (mail.html || "").replace(/<[^>]+>/g, " ")).slice(0, 20000);
    } catch (e) {
      console.log("본문 읽기 실패, 제목만 검사:", String(e));
    }
    const hits = badWords(subject + "\n" + body);
    if (hits.length >= 1) {
      // 버림: 보낸 사람에게 반송 메일도 보내지 않고 조용히 버려요. 기록은 Cloudflare 로그에만 남아요.
      console.log(`버림 ${message.to} ← ${message.from} | 제목: ${subject.slice(0, 60)} | 걸린 말: ${hits.slice(0, 5).join(", ")}`);
      return;
    }
    await message.forward(env.FORWARD_TO);
    console.log(`넘김 ${message.to} ← ${message.from} | 제목: ${subject.slice(0, 60)}`);
  },
};
