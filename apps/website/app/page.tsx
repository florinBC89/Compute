import Header from "@/components/Header";
import Hero from "@/components/Hero";
import BeforeAfter from "@/components/BeforeAfter";
import ComputeOverview from "@/components/ComputeOverview";
import WhereFrom from "@/components/WhereFrom";
import Footer from "@/components/Footer";

export default function HomePage() {
  return (
    <main className="relative overflow-hidden">
      <div className="glow-hero pointer-events-none absolute inset-x-0 top-0 h-[420px]" />
      <Header />
      <Hero />
      <BeforeAfter />
      <ComputeOverview />
      <WhereFrom />
      <Footer />
    </main>
  );
}
