/* Public landing page — what an anonymous visitor (and, critically, a Meta reviewer)
   sees at the root URL. Business verification and App Review both check that the
   website names the company, explains the product, states which data is used and why,
   and gives a working contact. A bare login screen fails all four. */

import { MessageCircle, Youtube, Instagram, Sparkles, ShieldCheck, Bell } from "lucide-react";

const COMPANY = "Aviora AI";
const PRODUCT = "MonitoringAI";
const CONTACT_EMAIL = "amirhonhodisaliev@gmail.com";

const FEATURES = [
  {
    icon: MessageCircle,
    title: "Telegram monitoring",
    text: "Kanal va guruhlardagi postlar hamda kommentlar real vaqtda yig'iladi.",
  },
  {
    icon: Youtube,
    title: "YouTube monitoring",
    text: "Kanal videolari va ulardagi kommentlar avtomatik kuzatiladi.",
  },
  {
    icon: Instagram,
    title: "Instagram monitoring",
    text: "Biznes akkauntingiz postlari va kommentlari — o'zingiz ruxsat bergan holda.",
  },
  {
    icon: Sparkles,
    title: "AI tahlil",
    text: "Har bir izoh kayfiyat va obro' xavfi bo'yicha baholanadi, qisqacha xulosa beriladi.",
  },
  {
    icon: Bell,
    title: "Tezkor ogohlantirish",
    text: "Yuqori xavfli izoh topilsa, mas'ul xodimga Telegram orqali darhol xabar boradi.",
  },
  {
    icon: ShieldCheck,
    title: "Ma'lumot xavfsizligi",
    text: "Ma'lumot sotilmaydi va reklama uchun ishlatilmaydi. Istalgan vaqtda o'chirish mumkin.",
  },
];

export function Landing() {
  return (
    <div className="landingPage">
      <header className="legalHead">
        <a className="legalBrand" href="/">{PRODUCT}</a>
        <nav className="legalNav">
          <a href="/privacy">Maxfiylik</a>
          <a href="/terms">Shartlar</a>
          <a href="/data-deletion">Ma'lumotni o'chirish</a>
          <a className="landingLoginLink" href="/login">Kirish</a>
        </nav>
      </header>

      <main className="landingBody">
        <section className="landingHero">
          <span className="landingEyebrow">{COMPANY}</span>
          <h1>Brendingiz haqida internetda nima deyilayotganini bir joyda ko'ring</h1>
          <p>
            {PRODUCT} — Telegram, YouTube va Instagram'dagi izohlarni avtomatik yig'ib, sun'iy intellekt
            yordamida kayfiyat va obro' xavfi bo'yicha tahlil qiladigan monitoring platformasi.
            Salbiy signal paydo bo'lishi bilan jamoangiz xabardor bo'ladi.
          </p>
          <a className="button primary landingCta" href="/login">Dashboardga kirish</a>
        </section>

        <section className="landingFeatures">
          {FEATURES.map(({ icon: Icon, title, text }) => (
            <article className="landingCard" key={title}>
              <Icon size={20} />
              <strong>{title}</strong>
              <span>{text}</span>
            </article>
          ))}
        </section>

        <section className="landingSteps">
          <h2>Qanday ishlaydi</h2>
          <ol>
            <li><strong>Ulaysiz.</strong> Brendingizni kiritasiz va kuzatiladigan kanal yoki akkauntlarni qo'shasiz.</li>
            <li><strong>Yig'ladi.</strong> Tizim yangi post va izohlarni avtomatik, uzluksiz to'playdi.</li>
            <li><strong>Tahlil qiladi.</strong> Har bir izoh AI orqali baholanadi: ijobiy/salbiy, xavf darajasi, tavsiya etilgan javob.</li>
            <li><strong>Ogohlantiradi.</strong> Xavfli signal topilsa, mas'ul xodimga darhol xabar yuboriladi.</li>
          </ol>
        </section>

        <section className="landingAbout">
          <h2>About {PRODUCT} (English)</h2>
          <p>
            {PRODUCT}, operated by {COMPANY}, is a social listening platform for brands. With the account
            owner's explicit consent, it reads the comments left on the brand's own social media accounts
            and analyses them for sentiment and reputational risk, so the brand's team can respond quickly.
          </p>
          <p>
            <strong>Instagram data usage.</strong> After the business owner authorises us through Business
            Login for Instagram, we read the connected professional account's own media and the comments on
            it. Comments are analysed and displayed only in that customer's private dashboard. We never sell
            data, never use it for advertising, and delete it when the account is disconnected. See our{" "}
            <a href="/privacy">Privacy Policy</a> and <a href="/data-deletion">Data Deletion</a> pages.
          </p>
        </section>

        <section className="landingContact">
          <h2>Aloqa / Contact</h2>
          <p>
            <strong>{COMPANY}</strong><br />
            Email: <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a><br />
            Veb: <a href="https://monitoring.avioraai.uz">monitoring.avioraai.uz</a>
          </p>
        </section>
      </main>

      <footer className="landingFooter">
        <span>© 2026 {COMPANY}</span>
        <nav className="legalNav">
          <a href="/privacy">Privacy</a>
          <a href="/terms">Terms</a>
          <a href="/data-deletion">Data deletion</a>
        </nav>
      </footer>
    </div>
  );
}
