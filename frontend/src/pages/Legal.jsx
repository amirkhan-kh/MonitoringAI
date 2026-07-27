/* Public legal pages. Meta App Review will not accept an app without a reachable
   privacy policy, terms of service and data-deletion route, and the reviewer opens them
   while logged out — so these render outside the dashboard's auth gate. */

// Public legal identity shown to Meta reviewers (must match Landing + Business verification).
const COMPANY = "Aviora AI";
const PRODUCT = "MonitoringAI";
const CONTACT_EMAIL = "avioraai1@gmail.com";
const UPDATED = "22.07.2026";

function LegalPage({ title, children }) {
  return (
    <div className="legalPage">
      <header className="legalHead">
        <a className="legalBrand" href="/">{PRODUCT}</a>
        <nav className="legalNav">
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="/data-deletion">Data deletion</a>
        </nav>
      </header>
      <main className="legalBody">
        <h1>{title}</h1>
        <p className="legalUpdated">Oxirgi yangilanish / Last updated: {UPDATED}</p>
        {children}
        <p className="legalContact">
          Savollar / Questions: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
        </p>
      </main>
    </div>
  );
}

export function PrivacyPolicy() {
  return (
    <LegalPage title="Maxfiylik siyosati / Privacy Policy">
      <h2>Qanday ma'lumot yig'amiz / What we collect</h2>
      <p>
        {COMPANY} ({PRODUCT}) — brendlar uchun ijtimoiy tarmoq monitoringi xizmati. Instagram akkaunti ulanganda biz
        Meta API orqali faqat quyidagilarni olamiz: akkauntning ochiq profil ma'lumoti (ID, username),
        o'sha akkauntning postlari va ularga yozilgan kommentlar matni, komment muallifining ochiq
        username'i va vaqt belgilari, hamda akkaunt egasi bergan kirish tokeni.
      </p>
      <p>
        We are a social listening service for brands. When an Instagram account is connected we access,
        via the official Meta API and only with the account owner's consent: the account's public profile
        (ID, username), the account's own media and the comments left on it, the commenter's public
        username and timestamps, and the access token granted to us.
      </p>

      <h2>Nima uchun / Why</h2>
      <p>
        Yig'ilgan kommentlar brend obro'sini kuzatish uchun sun'iy intellekt bilan tahlil qilinadi
        (kayfiyat, xavf darajasi, qisqacha xulosa) va faqat akkauntni ulagan mijozning shaxsiy panelida
        ko'rsatiladi. Comments are analysed by AI for sentiment and reputational risk and shown only in
        the dashboard of the customer who connected the account.
      </p>

      <h2>Kim ko'radi / Who sees it</h2>
      <p>
        Ma'lumot uchinchi shaxslarga sotilmaydi va reklama uchun ishlatilmaydi. U faqat xizmat ishlashi
        uchun zarur bo'lgan quyidagi qismlarga uzatiladi: bulutli AI tahlil provayderi (matn tahlili uchun)
        va bizning himoyalangan ma'lumotlar bazamiz. We never sell data or use it for advertising.
      </p>

      <h2>Qancha saqlanadi / Retention</h2>
      <p>
        Ma'lumot akkaunt ulangan holatda turgan vaqtda saqlanadi. Akkaunt panelda o'chirilsa yoki Meta
        orqali ruxsat bekor qilinsa, biz to'plangan kommentlar va tahlillarni o'chiramiz. Data is kept
        while the account stays connected and is deleted when it is disconnected.
      </p>

      <h2>Sizning huquqlaringiz / Your rights</h2>
      <p>
        Istalgan vaqtda ruxsatni Instagram sozlamalaridan bekor qilishingiz yoki{" "}
        <a href="/data-deletion">ma'lumotni o'chirish</a> sahifasi orqali barcha ma'lumotni o'chirishni
        so'rashingiz mumkin. You may revoke access at any time or request full deletion.
      </p>
    </LegalPage>
  );
}

export function TermsOfService() {
  return (
    <LegalPage title="Foydalanish shartlari / Terms of Service">
      <h2>Xizmat / The service</h2>
      <p>
        {COMPANY} mijozga o'zi egalik qiladigan yoki boshqarish huquqiga ega bo'lgan ijtimoiy tarmoq
        akkauntlaridagi kommentlarni yig'ish va AI yordamida tahlil qilish imkonini beradi.
        The service collects and analyses comments on social accounts the customer owns or is authorised
        to manage.
      </p>

      <h2>Foydalanuvchi majburiyatlari / Your responsibilities</h2>
      <ul>
        <li>
          Faqat o'zingiz egalik qiladigan yoki yozma ruxsat olgan akkauntni ulang.
          Only connect accounts you own or are authorised to manage.
        </li>
        <li>
          Meta platformasi qoidalarini va amaldagi qonunchilikni buzmang.
          Do not violate Meta platform policies or applicable law.
        </li>
        <li>
          Kirish ma'lumotlaringizni himoyalang. Keep your credentials secure.
        </li>
      </ul>

      <h2>Kafolatlar / Disclaimer</h2>
      <p>
        Xizmat "boricha" taqdim etiladi. AI tahlili maslahat xarakterida bo'lib, muhim qarorlar uchun
        yakuniy asos bo'la olmaydi. The service is provided "as is"; AI output is advisory.
      </p>

      <h2>Tugatish / Termination</h2>
      <p>
        Siz istalgan vaqtda akkauntni uzishingiz mumkin; shartlar buzilganda biz xizmatni to'xtatishimiz
        mumkin. You may disconnect at any time; we may suspend the service on breach of these terms.
      </p>
    </LegalPage>
  );
}

export function DataDeletion() {
  return (
    <LegalPage title="Ma'lumotni o'chirish / Data Deletion">
      <h2>Avtomatik o'chirish / Automatic deletion</h2>
      <p>
        Instagram sozlamalarida <strong>Settings → Apps and websites</strong> bo'limidan {COMPANY} ruxsatini
        bekor qilsangiz, Meta bizga xabar yuboradi va biz o'sha akkaunt bo'yicha saqlangan barcha
        kommentlar, tahlillar va tokenni o'chiramiz. Revoking access in Instagram triggers Meta's
        deauthorize callback and we delete everything stored for that account.
      </p>

      <h2>So'rov bilan o'chirish / Deletion by request</h2>
      <p>
        Ma'lumotni qo'lda o'chirtirish uchun <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a> ga
        Instagram username'ingizni yozib xat yuboring. So'rov 30 kun ichida bajariladi va sizga tasdiq
        yuboriladi. Email us with your Instagram username; we complete deletion within 30 days and confirm.
      </p>

      <h2>Nima o'chadi / What is deleted</h2>
      <ul>
        <li>Saqlangan kirish tokeni / the stored access token</li>
        <li>Yig'ilgan post va kommentlar matni / collected posts and comments</li>
        <li>Ular bo'yicha AI tahlil natijalari / the AI analyses derived from them</li>
      </ul>
    </LegalPage>
  );
}
