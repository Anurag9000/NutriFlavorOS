import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { motion, useScroll, useTransform } from "framer-motion";
import { Heart, Sparkles, Leaf, Palette, ArrowRight, CheckCircle2 } from "lucide-react";
import { AuroraBackground } from "@/components/ui/AuroraBackground";
import { MagneticButton } from "@/components/ui/MagneticButton";

const pillars = [
  { icon: Heart, title: "Health Optimization", desc: "AI-driven nutrition tracking that adapts to your body's needs and goals.", color: "text-health" },
  { icon: Palette, title: "Taste Satisfaction", desc: "Meals you actually enjoy. The system learns your flavor preferences over time.", color: "text-taste" },
  { icon: Sparkles, title: "Dietary Variety", desc: "Never eat the same thing twice. Explore cuisines, ingredients, and recipes.", color: "text-variety" },
  { icon: Leaf, title: "Sustainability", desc: "Minimize food waste and environmental impact with smart predictions.", color: "text-sustainability" },
];

const steps = [
  { num: "01", title: "Log Your Meals", desc: "Quick, intuitive meal logging. The system learns from every entry." },
  { num: "02", title: "AI Learns & Adapts", desc: "Our AI analyzes patterns, preferences, and nutritional balance." },
  { num: "03", title: "Get Personalized Plans", desc: "Receive optimized meal plans across all four pillars." },
  { num: "04", title: "Track & Improve", desc: "Monitor your progress with beautiful analytics and earn achievements." },
];

export default function Landing() {
  const { scrollY } = useScroll();
  // Reverted: Text moves DOWN naturally (Classic Parallax)
  const y1 = useTransform(scrollY, [0, 500], [0, 200]);

  // Kept: Image moves DOWN slightly to linger and fill the right side (as requested)
  const y2 = useTransform(scrollY, [0, 500], [0, 100]);

  return (
    <div className="min-h-screen bg-transparent overflow-hidden">
      <AuroraBackground />

      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 glass border-b border-white/10">
        <div className="max-w-7xl mx-auto flex items-center justify-between h-20 px-6">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-primary to-emerald-600 flex items-center justify-center text-white font-bold text-lg shadow-lg">N</div>
            <span className="font-bold text-xl tracking-tight">NutriFlavorOS</span>
          </div>
          <div className="flex items-center gap-4">
            <Button variant="ghost" className="hover:bg-white/10" asChild><Link to="/login">Log in</Link></Button>
            <MagneticButton>
              <Button asChild className="rounded-full px-8 shadow-lg shadow-primary/20"><Link to="/signup">Get Started</Link></Button>
            </MagneticButton>
          </div>
        </div>
      </nav>

      {/* Hero - Increased Bottom Padding for Gap */}
      <section className="relative pt-32 pb-28 px-6 min-h-screen flex items-center">
        <div className="max-w-7xl mx-auto grid lg:grid-cols-2 gap-16 items-center">
          <motion.div style={{ y: y1 }} initial={{ opacity: 0, x: -50 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.8, ease: "easeOut" }}>
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass border border-primary/20 text-primary text-sm font-medium mb-8">
              <Sparkles className="h-4 w-4" />
              <span>The Future of Nutrition is Here</span>
            </div>
            <h1 className="font-bold tracking-tight mb-6 leading-[1.1]">
              The Operating System <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary via-emerald-400 to-teal-500">
                For Your Metabolism
              </span>
            </h1>
            <p className="text-xl text-muted-foreground max-w-lg mb-10 leading-relaxed">
              NutriFlavorOS isn't just a calorie counter. It's an intelligent optimization engine for your health, taste, and lifestyle.
            </p>
            <div className="flex gap-4">
              <MagneticButton>
                <Button size="lg" className="h-14 px-8 rounded-full text-lg shadow-xl shadow-primary/25" asChild>
                  <Link to="/signup">Start Your Journey <ArrowRight className="ml-2 h-5 w-5" /></Link>
                </Button>
              </MagneticButton>
              <MagneticButton strength={15}>
                <Button size="lg" variant="outline" className="h-14 px-8 rounded-full text-lg border-primary/20 hover:bg-primary/5" asChild>
                  <Link to="/login">View Demo</Link>
                </Button>
              </MagneticButton>
            </div>

            <div className="mt-12 flex items-center gap-8 text-sm text-muted-foreground">
              <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-primary" /> AI-Powered Plans</div>
              <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-primary" /> Real-time Analytics</div>
              <div className="flex items-center gap-2"><CheckCircle2 className="h-4 w-4 text-primary" /> Zero Compromise</div>
            </div>
          </motion.div>

          <motion.div style={{ y: y2 }} initial={{ opacity: 0, scale: 0.8, rotate: -5 }} animate={{ opacity: 1, scale: 1, rotate: 0 }} transition={{ duration: 1, delay: 0.2 }} className="relative hidden lg:block">
            {/* Visual Abstract Composition */}
            <div className="relative w-full aspect-square max-w-[600px] mx-auto">
              <div className="absolute inset-0 bg-gradient-to-tr from-primary/30 to-purple-500/30 rounded-full blur-[100px] animate-pulse-glow" />

              {/* Added: Extra Density Element to fill right side */}
              <motion.div animate={{ rotate: [0, 10, 0] }} transition={{ duration: 20, repeat: Infinity, ease: "linear" }}
                className="absolute -top-10 -right-10 w-32 h-32 rounded-full border border-white/10 glass z-0 opacity-50" />

              {/* Glass Cards Floating */}
              <motion.div animate={{ y: [0, -20, 0] }} transition={{ duration: 6, repeat: Infinity, ease: "easeInOut" }}
                className="absolute top-10 right-10 z-20 glass-card p-4 rounded-2xl w-48 shadow-2xl border-white/20">
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-10 w-10 rounded-full bg-orange-100 flex items-center justify-center text-orange-600"><Heart className="h-5 w-5" /></div>
                  <div>
                    <p className="text-xs text-muted-foreground">Health Score</p>
                    <p className="font-bold text-lg">98/100</p>
                  </div>
                </div>
                <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden"><div className="h-full bg-orange-500 w-[98%]" /></div>
              </motion.div>

              <motion.div animate={{ y: [0, 20, 0] }} transition={{ duration: 7, repeat: Infinity, ease: "easeInOut", delay: 1 }}
                className="absolute bottom-20 left-0 z-20 glass-card p-4 rounded-2xl w-56 shadow-2xl border-white/20">
                <div className="flex items-center gap-3 mb-2">
                  <div className="h-10 w-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600"><Leaf className="h-5 w-5" /></div>
                  <div>
                    <p className="text-xs text-muted-foreground">Carbon Saved</p>
                    <p className="font-bold text-lg">12.5 kg CO₂</p>
                  </div>
                </div>
              </motion.div>

              {/* Added: Extra floating badge for density */}
              <motion.div animate={{ x: [0, 10, 0] }} transition={{ duration: 5, repeat: Infinity, ease: "easeInOut", delay: 2 }}
                className="absolute top-1/2 -right-8 z-30 glass px-4 py-2 rounded-full border border-white/20 shadow-xl">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
                  AI Active
                </div>
              </motion.div>

              {/* Main abstract food image placeholder - Scaled up slightly for less empty space */}
              <img
                src="https://images.unsplash.com/photo-1546069901-ba9599a7e63c?q=80&w=1000&auto=format&fit=crop"
                alt="Healthy Food Art"
                className="relative z-10 w-full h-full object-cover rounded-[3rem] shadow-2xl rotate-3 hover:rotate-0 transition-transform duration-700 hover:scale-[1.02]"
              />
            </div>
          </motion.div>
        </div>
      </section>

      {/* Pillars - Increased spacing z-index fix */}
      <section className="max-w-7xl mx-auto pt-32 pb-12 px-6 relative z-20 mt-0 mb-0">
        <motion.div initial={{ opacity: 0, y: 50 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-100px" }} className="text-center mb-24">
          <h2 className="text-4xl md:text-5xl font-bold mb-6">Four Pillars of Perfection</h2>
          <p className="text-xl text-muted-foreground max-w-2xl mx-auto">We don't balance your diet. We optimize your entire nutritional existence.</p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
          {pillars.map((p, i) => (
            <motion.div key={p.title} initial={{ opacity: 0, y: 30 }} whileInView={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.1 }} viewport={{ once: true }}
              whileHover={{ y: -10 }}
              className="glass-card p-8 rounded-3xl relative overflow-hidden group">
              <div className={`absolute top-0 right-0 p-32 bg-current opacity-5 blur-[60px] rounded-full group-hover:opacity-10 transition-opacity ${p.color}`} />
              <div className="relative z-10">
                <div className={`h-14 w-14 rounded-2xl glass flex items-center justify-center mb-6 text-2xl group-hover:scale-110 transition-transform duration-500 ${p.color}`}>
                  <p.icon className="h-7 w-7" />
                </div>
                <h3 className="text-xl font-bold mb-3">{p.title}</h3>
                <p className="text-muted-foreground leading-relaxed">{p.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="pt-12 pb-32 px-6 relative overflow-hidden">
        <div className="absolute inset-0 bg-secondary/30 skew-y-3 transform origin-top-left scale-110" />
        <div className="max-w-6xl mx-auto relative z-10">
          <motion.div initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }} className="text-center mb-20">
            <h2 className="text-4xl font-bold mb-6">Intelligence In Action</h2>
          </motion.div>

          <div className="grid md:grid-cols-2 gap-16">
            {steps.map((s, i) => (
              <motion.div key={s.num} initial={{ opacity: 0, x: i % 2 === 0 ? -50 : 50 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                className="flex gap-6 group">
                <span className="text-6xl font-black text-transparent bg-clip-text bg-gradient-to-br from-primary/20 to-transparent group-hover:from-primary/40 transition-all duration-500">
                  {s.num}
                </span>
                <div className="pt-4">
                  <h3 className="text-2xl font-bold mb-3 group-hover:text-primary transition-colors">{s.title}</h3>
                  <p className="text-lg text-muted-foreground">{s.desc}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="max-w-5xl mx-auto py-32 px-6 text-center relative">
        <div className="absolute inset-0 bg-gradient-to-r from-primary/10 via-purple-500/10 to-teal-500/10 blur-3xl" />
        <motion.div initial={{ opacity: 0, scale: 0.9 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}
          className="glass-card p-16 rounded-[3rem] relative z-10 border-white/20">
          <h2 className="text-4xl md:text-6xl font-bold mb-8">Ready to Upgrade Your Life?</h2>
          <p className="text-xl text-muted-foreground mb-12 max-w-2xl mx-auto">
            Join the thousands of users who have stopped counting calories and started optimizing their existence with NutriFlavorOS.
          </p>
          <div className="flex flex-col sm:flex-row gap-6 justify-center">
            <MagneticButton strength={40}>
              <Button size="lg" className="h-16 px-10 rounded-full text-xl shadow-2xl hover:scale-105 transition-transform" asChild>
                <Link to="/signup">Get Started Now</Link>
              </Button>
            </MagneticButton>
          </div>
          <p className="mt-8 text-sm text-muted-foreground">No credit card required for standard tier.</p>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="border-t border-white/5 py-12 text-center text-sm text-muted-foreground bg-black/20 backdrop-blur-lg">
        <div className="flex items-center justify-center gap-2 mb-4 opacity-50">
          <div className="h-6 w-6 rounded bg-primary/50" />
          <span className="font-semibold">NutriFlavorOS</span>
        </div>
        <p>© 2026 NutriFlavorOS. Designed for the Future.</p>
      </footer>
    </div>
  );
}
