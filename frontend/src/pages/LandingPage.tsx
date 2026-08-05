import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  MessageSquareText,
  FileText,
  PenTool,
  Mic,
  BarChart3,
  Download,
  ArrowRight,
  Sparkles,
  Zap,
  Shield,
  Brain,
} from 'lucide-react';

const features = [
  {
    icon: MessageSquareText,
    title: 'AI Career Agent',
    description:
      'Conversational assistant with tool-calling, session memory, and real-time streaming responses.',
    gradient: 'from-[#7C9AF5] to-[#60A5FA]',
    delay: 0,
  },
  {
    icon: FileText,
    title: 'Resume Tailoring',
    description:
      'Upload your resume + job description → get an ATS-optimized, tailored version with skills breakdown.',
    gradient: 'from-[#A78BFA] to-[#7C9AF5]',
    delay: 100,
  },
  {
    icon: PenTool,
    title: 'Cover Letters',
    description:
      'Generate tailored, 3-paragraph cover letters based on your resume and target role context.',
    gradient: 'from-[#F472B6] to-[#A78BFA]',
    delay: 200,
  },
  {
    icon: Mic,
    title: 'Interview Prep',
    description:
      'Role-specific questions with STAR-format answers, personalized with your project experience.',
    gradient: 'from-[#FBBF24] to-[#F472B6]',
    delay: 300,
  },
  {
    icon: BarChart3,
    title: 'ATS Score',
    description:
      'Real-time compatibility scoring with visual ring indicator showing 0–100 match percentage.',
    gradient: 'from-[#34D399] to-[#7C9AF5]',
    delay: 400,
  },
  {
    icon: Download,
    title: 'PDF Export',
    description:
      'Download your tailored resume as a polished, professionally formatted PDF document.',
    gradient: 'from-[#60A5FA] to-[#34D399]',
    delay: 500,
  },
];

const stats = [
  { value: '10K+', label: 'Resumes Tailored' },
  { value: '95%', label: 'ATS Pass Rate' },
  { value: '4.9/5', label: 'User Rating' },
  { value: '<2s', label: 'Response Time' },
];

function useInView(threshold = 0.1) {
  const ref = useRef<HTMLDivElement>(null);
  const [isInView, setIsInView] = useState(false);

  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsInView(true);
          observer.disconnect();
        }
      },
      { threshold }
    );

    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [threshold]);

  return { ref, isInView };
}

function AnimatedCounter({ value, isInView }: { value: string; isInView: boolean }) {
  const [displayed, setDisplayed] = useState('0');

  useEffect(() => {
    if (!isInView) return;

    const numericPart = parseInt(value.replace(/[^0-9]/g, '')) || 0;
    const suffixPart = value.replace(/[0-9.]/g, '');
    const animDuration = 2000;
    const animStart = performance.now();

    const tick = (now: number) => {
      const elapsed = now - animStart;
      const t = Math.min(elapsed / animDuration, 1);
      const easedT = 1 - Math.pow(1 - t, 3);
      const current = Math.round(easedT * numericPart);
      setDisplayed(current + suffixPart);
      if (t < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [isInView, value]);

  return <span>{displayed}</span>;
}

export default function LandingPage() {
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const heroRef = useInView(0.1);
  const featuresRef = useInView(0.05);
  const statsRef = useInView(0.1);
  const ctaRef = useInView(0.1);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({
        x: (e.clientX / window.innerWidth - 0.5) * 20,
        y: (e.clientY / window.innerHeight - 0.5) * 20,
      });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  return (
    <div className="min-h-screen bg-bg-base overflow-x-hidden">
      {/* Ambient Background */}
      <div className="fixed inset-0 pointer-events-none">
        <div
          className="absolute top-[-20%] left-[-10%] w-[60%] h-[60%] rounded-full opacity-20 blur-[120px] animate-pulse-slow"
          style={{ background: 'radial-gradient(circle, #6C8EF5 0%, transparent 70%)' }}
        />
        <div
          className="absolute bottom-[-20%] right-[-10%] w-[50%] h-[50%] rounded-full opacity-15 blur-[100px] animate-pulse-slow animation-delay-2000"
          style={{ background: 'radial-gradient(circle, #A78BFA 0%, transparent 70%)' }}
        />
        <div
          className="absolute top-[40%] right-[20%] w-[30%] h-[30%] rounded-full opacity-10 blur-[80px] animate-pulse-slow animation-delay-4000"
          style={{ background: 'radial-gradient(circle, #34D399 0%, transparent 70%)' }}
        />
      </div>

      {/* Grid Pattern */}
      <div
        className="fixed inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage: `linear-gradient(rgba(108,142,245,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(108,142,245,0.3) 1px, transparent 1px)`,
          backgroundSize: '60px 60px',
        }}
      />

      {/* Navigation */}
      <nav className="relative z-50 flex items-center justify-between px-6 md:px-12 py-5">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-accent to-violet-500 flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="text-lg font-semibold text-text-primary tracking-tight">
            CareerAI
          </span>
        </div>
        <div className="hidden md:flex items-center gap-8">
          <a href="#features" className="text-sm text-text-secondary hover:text-text-primary transition-colors duration-300">
            Features
          </a>
          <a href="#stats" className="text-sm text-text-secondary hover:text-text-primary transition-colors duration-300">
            Results
          </a>
          <a href="#cta" className="text-sm text-text-secondary hover:text-text-primary transition-colors duration-300">
            Get Started
          </a>
        </div>
        <Link
          to="/chat"
          className="px-4 py-2 text-sm font-medium rounded-lg bg-accent/10 text-accent border border-accent/20 hover:bg-accent/20 transition-all duration-300"
        >
          Launch App
        </Link>
      </nav>

      {/* Hero Section */}
      <section className="relative z-10 flex flex-col items-center justify-center min-h-[85vh] px-6 text-center">
        <div
          ref={heroRef.ref}
          className={`transition-all duration-1000 ${
            heroRef.isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
          }`}
        >
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-4 py-1.5 mb-8 rounded-full bg-accent/5 border border-accent/20 backdrop-blur-sm">
            <Zap className="w-3.5 h-3.5 text-accent" />
            <span className="text-xs font-medium text-accent">
              Powered by Advanced AI Agents
            </span>
          </div>

          {/* Main Heading */}
          <h1 className="text-5xl md:text-7xl lg:text-8xl font-bold tracking-tight leading-[1.05] mb-6">
            <span className="block text-text-primary animate-fade-in-up">
              Land Your Dream
            </span>
            <span className="block mt-2 animate-fade-in-up animation-delay-200">
              <span className="bg-gradient-to-r from-accent via-[#A78BFA] to-[#60A5FA] bg-clip-text text-transparent">
                Job with AI
              </span>
            </span>
          </h1>

          {/* Subtitle */}
          <p
            className={`max-w-2xl mx-auto text-lg md:text-xl text-text-secondary leading-relaxed mb-10 animate-fade-in-up animation-delay-400 transition-all duration-1000 ${
              heroRef.isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
            }`}
          >
            An intelligent career assistant that tailors resumes, generates cover
            letters, prepares you for interviews, and answers career questions —
            all through a conversational AI agent.
          </p>

          {/* CTA Buttons */}
          <div
            className={`flex flex-col sm:flex-row items-center justify-center gap-4 animate-fade-in-up animation-delay-600 transition-all duration-1000 ${
              heroRef.isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-5'
            }`}
          >
            <Link
              to="/chat"
              className="group relative px-8 py-3.5 rounded-xl bg-accent text-white font-medium text-sm overflow-hidden transition-all duration-300 hover:shadow-[0_0_40px_rgba(108,142,245,0.3)] hover:scale-105"
            >
              <span className="relative z-10 flex items-center gap-2">
                Start Free
                <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
              </span>
              <div className="absolute inset-0 bg-gradient-to-r from-accent to-violet-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
            </Link>
            <a
              href="#features"
              className="px-8 py-3.5 rounded-xl border border-border text-text-secondary font-medium text-sm hover:border-accent/50 hover:text-text-primary transition-all duration-300"
            >
              Explore Features
            </a>
          </div>
        </div>

        {/* Floating Elements */}
        <div
          className="absolute top-20 left-10 w-16 h-16 rounded-2xl bg-accent/5 border border-accent/10 backdrop-blur-sm flex items-center justify-center animate-float"
          style={{
            transform: `translate(${mousePos.x * 0.5}px, ${mousePos.y * 0.5}px)`,
          }}
        >
          <Brain className="w-6 h-6 text-accent/60" />
        </div>
        <div
          className="absolute bottom-32 right-16 w-14 h-14 rounded-2xl bg-violet-500/5 border border-violet-500/10 backdrop-blur-sm flex items-center justify-center animate-float animation-delay-1000"
          style={{
            transform: `translate(${mousePos.x * -0.3}px, ${mousePos.y * -0.3}px)`,
          }}
        >
          <Shield className="w-5 h-5 text-violet-400/60" />
        </div>
        <div
          className="absolute top-40 right-20 w-12 h-12 rounded-full bg-emerald-500/5 border border-emerald-500/10 backdrop-blur-sm flex items-center justify-center animate-float animation-delay-2000"
          style={{
            transform: `translate(${mousePos.x * 0.4}px, ${mousePos.y * -0.4}px)`,
          }}
        >
          <Sparkles className="w-4 h-4 text-emerald-400/60" />
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="relative z-10 py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div
            ref={featuresRef.ref}
            className={`text-center mb-16 transition-all duration-1000 ${
              featuresRef.isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
            }`}
          >
            <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-4">
              Everything You Need to{' '}
              <span className="bg-gradient-to-r from-accent via-[#A78BFA] to-[#60A5FA] bg-clip-text text-transparent">
                Get Hired
              </span>
            </h2>
            <p className="text-text-secondary text-lg max-w-2xl mx-auto">
              From resume optimization to interview preparation — our AI handles
              the heavy lifting so you can focus on what matters.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {features.map((feature) => (
              <FeatureCard key={feature.title} feature={feature} />
            ))}
          </div>
        </div>
      </section>

      {/* Stats Section */}
      <section id="stats" className="relative z-10 py-24 px-6">
        <div
          ref={statsRef.ref}
          className={`max-w-5xl mx-auto transition-all duration-1000 ${
            statsRef.isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
          }`}
        >
          <div className="relative rounded-3xl border border-border bg-bg-surface/50 backdrop-blur-xl p-12 md:p-16 overflow-hidden">
            {/* Background glow */}
            <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[60%] h-px bg-gradient-to-r from-transparent via-accent/50 to-transparent" />

            <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
              {stats.map((stat) => (
                <div key={stat.label} className="text-center">
                  <div className="text-3xl md:text-4xl font-bold text-text-primary mb-2">
                    <AnimatedCounter value={stat.value} isInView={statsRef.isInView} />
                  </div>
                  <div className="text-sm text-text-secondary">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section id="cta" className="relative z-10 py-24 px-6">
        <div
          ref={ctaRef.ref}
          className={`max-w-4xl mx-auto text-center transition-all duration-1000 ${
            ctaRef.isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-10'
          }`}
        >
          <div className="relative rounded-3xl border border-border bg-gradient-to-b from-bg-surface/80 to-bg-base/50 backdrop-blur-xl p-12 md:p-20 overflow-hidden">
            {/* Animated border glow */}
            <div className="absolute inset-0 rounded-3xl animate-glow" />

            <div className="relative z-10">
              <h2 className="text-3xl md:text-5xl font-bold text-text-primary mb-6">
                Ready to Transform Your{' '}
                <span className="bg-gradient-to-r from-accent via-[#A78BFA] to-[#60A5FA] bg-clip-text text-transparent">
                  Job Search?
                </span>
              </h2>
              <p className="text-text-secondary text-lg mb-10 max-w-xl mx-auto">
                Join thousands of professionals who landed their dream roles with
                AI-powered career assistance.
              </p>
              <Link
                to="/chat"
                className="group inline-flex items-center gap-2 px-10 py-4 rounded-xl bg-accent text-white font-medium text-base overflow-hidden transition-all duration-300 hover:shadow-[0_0_60px_rgba(108,142,245,0.4)] hover:scale-105"
              >
                <span className="relative z-10 flex items-center gap-2">
                  Get Started Free
                  <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
                </span>
                <div className="absolute inset-0 bg-gradient-to-r from-accent to-violet-500 opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-accent to-violet-500 flex items-center justify-center">
              <Sparkles className="w-3 h-3 text-white" />
            </div>
            <span className="text-sm font-medium text-text-secondary">
              CareerAI
            </span>
          </div>
          <p className="text-xs text-text-secondary/60">
            Built with React, FastAPI & LangGraph — AI-powered career assistance
          </p>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  feature,
}: {
  feature: (typeof features)[0];
}) {
  const { ref, isInView } = useInView(0.1);

  return (
    <div
      ref={ref}
      className={`group relative rounded-2xl border border-border bg-bg-surface/30 backdrop-blur-sm p-6 transition-all duration-700 hover:border-accent/30 hover:bg-bg-surface/60 hover:shadow-[0_0_40px_rgba(108,142,245,0.08)] ${
        isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
      }`}
      style={{ transitionDelay: `${feature.delay}ms` }}
    >
      {/* Icon */}
      <div
        className={`w-12 h-12 rounded-xl bg-gradient-to-br ${feature.gradient} flex items-center justify-center mb-4 group-hover:scale-110 transition-transform duration-300`}
      >
        <feature.icon className="w-5 h-5 text-white" />
      </div>

      {/* Content */}
      <h3 className="text-lg font-semibold text-text-primary mb-2">
        {feature.title}
      </h3>
      <p className="text-sm text-text-secondary leading-relaxed">
        {feature.description}
      </p>
    </div>
  );
}
