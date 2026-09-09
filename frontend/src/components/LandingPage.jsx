function LandingPage() {
  return (
    <>
    <header className="fixed top-0 w-full z-50 bg-background/80 backdrop-blur-xl shadow-[0_1px_8px_rgba(0,242,255,0.05)]"><div className="h-20 w-full px-margin-desktop flex items-center justify-between mx-auto max-w-container-max"><div className="flex items-center gap-4"><img alt="VoiceGuard Logo" className="h-8 w-auto object-contain" src="/logo.png"/><span className="font-headline-md text-headline-md text-on-surface tracking-tight">VoiceGuard</span></div><nav className="hidden lg:flex items-center gap-10"><a aria-current="page" className="transition-colors text-primary-container font-bold" href="#">Product</a><a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors" href="#">Features</a><a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary transition-colors" href="#">Technology</a><a className="bg-primary text-on-primary font-label-caps text-label-caps px-6 py-3 rounded-xl hover:bg-primary-container transition-all shadow-[0_0_20px_rgba(0,219,231,0.2)]" href="#">Book a Demo</a></nav><div className="flex items-center gap-4 lg:hidden"><span className="material-symbols-outlined text-on-surface">menu</span></div><div className="hidden lg:flex items-center ml-4"><div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center"><span className="material-symbols-outlined text-on-primary text-[18px]">person</span></div></div></div></header>
    <main className="w-full pt-20 bg-background">
    <div className="flex flex-col w-full text-on-surface bg-[#0a0a0f] overflow-x-hidden selection:bg-primary-container selection:text-on-primary font-body-md">

    {/* 1. HERO SECTION */}
    <section className="relative min-h-[90vh] flex flex-col items-center justify-center pt-32 pb-24 px-margin-mobile md:px-margin-desktop max-w-container-max mx-auto w-full z-10">
    <div className="absolute inset-0 pointer-events-none -z-10 flex items-center justify-center opacity-30">
    <div className="w-[800px] h-[800px] rounded-full bg-primary/5 blur-[120px] mix-blend-screen"></div>
    </div>
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 lg:gap-24 items-center w-full">
    <div className="flex flex-col gap-8 max-w-2xl z-20">
    <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full glass-panel self-start border-t border-t-primary/30">
    <div className="w-2 h-2 rounded-full bg-primary pulse-dot"></div>
    <span className="font-label-caps text-label-caps text-primary tracking-widest uppercase">System Active // Shield Online</span>
    </div>
    <h1 className="font-headline-xl text-headline-lg-mobile md:text-headline-xl text-on-surface leading-tight tracking-tight">
                        Your voice can be faked in <span className="text-transparent bg-clip-text bg-gradient-to-r from-primary to-primary-container glow-text">seconds.</span>
    </h1>
    <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl">
                        Detect AI voice clones in real-time. Protect your organization from the next generation of social engineering attacks with cryptographically verified vocal signatures.
                    </p>
    <div className="flex flex-col sm:flex-row gap-4 mt-4">
    <button className="bg-primary text-on-primary font-label-caps text-label-caps px-8 py-4 rounded-xl hover:bg-primary-container hover:shadow-[0_0_30px_rgba(0,219,231,0.4)] transition-all duration-300 uppercase tracking-widest flex items-center justify-center gap-2">
                            See it in action
                            <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
    </button>
    <button className="glass-panel text-on-surface font-label-caps text-label-caps px-8 py-4 rounded-xl hover:bg-surface-container-high transition-all duration-300 uppercase tracking-widest flex items-center justify-center gap-2">
    <span className="material-symbols-outlined text-[18px]">code</span>
                            API Docs
                        </button>
    </div>
    <div className="mt-8 flex items-center gap-4 text-on-surface-variant/50 font-data-display text-[12px]">
    <span className="material-symbols-outlined text-[16px]">verified_user</span>
    <span>ENTERPRISE GRADE SECURITY // SOC2 COMPLIANT</span>
    </div>
    </div>
    <div className="relative w-full flex justify-center z-20">
    <div className="relative w-full max-w-[400px] aspect-[0.75] rounded-3xl overflow-hidden shadow-2xl shadow-primary/20 ring-1 ring-primary/20 transform rotate-2 hover:rotate-0 transition-transform duration-700">
    <img alt="VoiceGuard Security Phone Mockup" className="w-full h-full object-cover" src="/phone-mockup.png"/>
    <div className="scanning-line z-30"></div>
    <div className="absolute inset-0 bg-gradient-to-t from-[#0a0a0f] via-transparent to-transparent opacity-60"></div>
    </div>
    </div>
    </div>
    </section>

    {/* 2. PROBLEM SECTION */}
    <section className="py-32 px-margin-mobile md:px-margin-desktop w-full relative z-10 border-t border-white/5">
    <div className="max-w-container-max mx-auto w-full grid grid-cols-1 lg:grid-cols-12 gap-16">
    <div className="lg:col-span-5 flex flex-col justify-center gap-12">
    <div>
    <h2 className="font-label-caps text-label-caps text-error tracking-widest mb-4 uppercase">The Threat Landscape</h2>
    <h3 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface leading-tight">
                            Deepfakes are indistinguishable from reality.
                        </h3>
    </div>
    <div className="flex flex-col gap-6">
    <div className="glass-panel p-6 rounded-2xl border-l-4 border-l-error">
    <div className="font-headline-xl text-error mb-2">3s</div>
    <p className="font-data-display text-data-display text-on-surface-variant uppercase tracking-wider">Audio needed to clone a voice</p>
    </div>
    <div className="glass-panel p-6 rounded-2xl border-l-4 border-l-error-container">
    <div className="font-headline-xl text-error-container mb-2">90%</div>
    <p className="font-data-display text-data-display text-on-surface-variant uppercase tracking-wider">Of CEO fraud uses AI clones</p>
    </div>
    </div>
    </div>
    <div className="lg:col-span-7 relative">
    <div className="glass-panel rounded-3xl p-8 h-full min-h-[500px] relative overflow-hidden group">
    <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 bg-error/20 rounded-full blur-[80px] transition-opacity duration-1000 group-hover:opacity-100 opacity-50"></div>
    <div className="relative z-10 h-full flex flex-col">
    <div className="flex justify-between items-center mb-12 border-b border-white/10 pb-6">
    <div className="flex items-center gap-4">
    <div className="w-12 h-12 rounded-full bg-surface-container flex items-center justify-center">
    <span className="material-symbols-outlined text-on-surface">person</span>
    </div>
    <div>
    <div className="font-headline-md text-on-surface">Incoming Call</div>
    <div className="font-data-display text-on-surface-variant text-sm">ID: UNKNOWN_ORIGIN</div>
    </div>
    </div>
    <div className="bg-error/10 text-error px-4 py-2 rounded-full font-label-caps text-[10px] border border-error/30 flex items-center gap-2">
    <span className="w-2 h-2 rounded-full bg-error animate-pulse"></span>
                                     HIGH RISK
                                 </div>
    </div>
    <div className="flex-1 flex flex-col justify-center items-center">
    <svg className="w-full h-32 text-error opacity-80" preserveAspectRatio="none" viewBox="0 0 400 100">
    <path className="opacity-50" d="M0,50 Q20,20 40,50 T80,50 T120,30 T160,70 T200,10 T240,90 T280,40 T320,60 T360,20 T400,50" fill="none" stroke="currentColor" strokeWidth="2"></path>
    <path d="M0,50 Q30,80 60,50 T120,50 T180,20 T240,80 T300,10 T360,90 T400,50" fill="none" stroke="currentColor" strokeWidth="1"></path>
    </svg>
    <div className="mt-12 w-full max-w-sm glass-panel p-6 rounded-xl border-error/40 shadow-[0_0_30px_rgba(255,180,171,0.1)]">
    <div className="flex justify-between items-end mb-2">
    <span className="font-label-caps text-error tracking-widest">AI Probability</span>
    <span className="font-headline-md text-error">98.4%</span>
    </div>
    <div className="w-full h-1 bg-surface-container rounded-full overflow-hidden">
    <div className="h-full bg-error w-[98%]" style={{boxShadow: '0 0 10px currentColor'}}></div>
    </div>
    <div className="mt-6 flex flex-col gap-3 font-data-display text-[12px] text-on-surface-variant">
    <div className="flex items-center justify-between">
    <span>&gt; FREQUENCY_ANALYSIS</span>
    <span className="text-error">SYNTHETIC</span>
    </div>
    <div className="flex items-center justify-between">
    <span>&gt; MICRO_TREMORS</span>
    <span className="text-error">ABSENT</span>
    </div>
    <div className="flex items-center justify-between">
    <span>&gt; CONTEXT_FLAGS</span>
    <span className="text-error-container">URGENCY DETECTED</span>
    </div>
    </div>
    </div>
    </div>
    </div>
    </div>
    </div>
    </div>
    </section>

    {/* 3. HOW IT WORKS */}
    <section className="py-32 relative z-10">
    <div className="max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop w-full flex flex-col items-center">
    <div className="text-center max-w-3xl mb-24">
    <h2 className="font-label-caps text-label-caps text-primary tracking-widest mb-4 uppercase">The Secure Core Architecture</h2>
    <h3 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface leading-tight">
                        Multi-layered verification in milliseconds.
                    </h3>
    </div>
    <div className="grid grid-cols-1 md:grid-cols-3 gap-8 w-full relative">
    <div className="hidden md:block absolute top-1/2 left-[16%] right-[16%] h-px bg-gradient-to-r from-transparent via-primary/30 to-transparent -translate-y-1/2 z-0"></div>
    <div className="glass-panel p-8 rounded-3xl relative z-10 flex flex-col h-full transform md:translate-y-12">
    <div className="text-primary-container font-headline-xl opacity-20 mb-4 font-data-display">01</div>
    <h4 className="font-headline-md text-on-surface mb-4">Fusion Scoring</h4>
    <p className="font-body-md text-on-surface-variant flex-1 mb-8">
                            Real-time analysis of vocal tract geometry, cadence, and contextual semantics against known baselines.
                        </p>
    <div className="h-32 rounded-xl bg-surface-container overflow-hidden relative flex items-center justify-center border border-white/5">
    <svg className="w-full h-full text-primary/40 p-4" viewBox="0 0 200 100">
    <circle className="animate-[spin_10s_linear_infinite]" cx="100" cy="50" fill="none" r="40" stroke="currentColor" strokeDasharray="4 4" strokeWidth="1"></circle>
    <circle className="animate-[spin_6s_linear_infinite_reverse]" cx="100" cy="50" fill="none" r="30" stroke="currentColor" strokeWidth="2"></circle>
    <text fill="currentColor" fontFamily="monospace" fontSize="12" textAnchor="middle" x="100" y="55">SYNC</text>
    </svg>
    </div>
    </div>
    <div className="glass-panel p-2 rounded-3xl relative z-20 shadow-2xl shadow-primary/10 border-t-primary/30 h-[600px] flex flex-col bg-surface/90">
    <div className="absolute -top-4 left-1/2 -translate-x-1/2 bg-[#0a0a0f] px-4 py-1 rounded-full border border-primary/30 font-label-caps text-primary text-[10px] uppercase tracking-widest z-30">Active Protocol</div>
    <div className="w-full h-full rounded-2xl bg-surface-container-lowest border border-white/5 overflow-hidden flex flex-col p-6 relative">
    <div className="text-center mb-8 mt-4">
    <div className="font-data-display text-on-surface-variant text-sm mb-2 uppercase">Challenge Requested</div>
    <div className="font-headline-lg text-primary tracking-widest font-data-display">4-7-2-9</div>
    </div>
    <div className="flex-1 flex flex-col items-center justify-center relative">
    <div className="relative w-48 h-48 flex items-center justify-center">
    <div className="absolute inset-0 rounded-full border border-error/20 animate-ping"></div>
    <div className="absolute inset-4 rounded-full border border-error/40 animate-pulse"></div>
    <div className="w-32 h-32 rounded-full bg-error/10 border border-error/50 flex flex-col items-center justify-center backdrop-blur-md z-10 shadow-[0_0_40px_rgba(255,180,171,0.2)]">
    <span className="material-symbols-outlined text-error text-[32px] mb-1">mic</span>
    <span className="font-data-display text-[10px] text-error uppercase">Listening...</span>
    </div>
    </div>
    </div>
    <div className="w-full bg-error/20 border border-error/50 p-4 rounded-xl text-center backdrop-blur-sm mt-8">
    <div className="font-label-caps text-error tracking-widest uppercase mb-1">Fail: Clone Detected</div>
    <div className="font-data-display text-[10px] text-error-container">SIGNATURE MISMATCH ON DIGIT '7'</div>
    </div>
    </div>
    </div>
    <div className="glass-panel p-8 rounded-3xl relative z-10 flex flex-col h-full transform md:translate-y-12">
    <div className="text-primary-container font-headline-xl opacity-20 mb-4 font-data-display">03</div>
    <h4 className="font-headline-md text-on-surface mb-4">Immutable Ledger</h4>
    <p className="font-body-md text-on-surface-variant flex-1 mb-8">
                            Every interaction is hashed and stored securely, providing an unalterable audit trail for compliance.
                        </p>
    <div className="h-32 rounded-xl bg-surface-container p-4 overflow-hidden relative border border-white/5 font-data-display text-[10px] text-on-surface-variant break-all flex items-end">
                             0x8f9a2c...<br/>
                             VERIFIED_TIMESTAMP: 1716382901<br/>
                             STATUS: <span className="text-primary">SECURE</span>
    <div className="absolute top-0 left-0 w-full h-full bg-gradient-to-b from-surface-container to-transparent opacity-80"></div>
    </div>
    </div>
    </div>
    </div>
    </section>

    {/* 5. TRUST STRIP */}
    <section className="py-24 border-y border-white/5 bg-surface-container-lowest/50 relative overflow-hidden">
    <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-primary/5 via-[#0a0a0f] to-[#0a0a0f] -z-10"></div>
    <div className="max-w-container-max mx-auto px-margin-mobile md:px-margin-desktop w-full">
    <div className="grid grid-cols-2 md:grid-cols-4 gap-8 divide-x divide-white/5 text-center">
    <div className="px-4">
    <div className="font-headline-xl text-on-surface mb-2 tracking-tighter">99.9%</div>
    <div className="font-data-display text-[12px] text-on-surface-variant uppercase tracking-widest">Accuracy</div>
    </div>
    <div className="px-4">
    <div className="font-headline-xl text-on-surface mb-2 tracking-tighter">&lt;50ms</div>
    <div className="font-data-display text-[12px] text-on-surface-variant uppercase tracking-widest">Latency</div>
    </div>
    <div className="px-4">
    <div className="font-headline-xl text-on-surface mb-2 tracking-tighter">25+</div>
    <div className="font-data-display text-[12px] text-on-surface-variant uppercase tracking-widest">Languages</div>
    </div>
    <div className="px-4">
    <div className="font-headline-xl text-on-surface mb-2 tracking-tighter">0</div>
    <div className="font-data-display text-[12px] text-on-surface-variant uppercase tracking-widest">False Positives</div>
    </div>
    </div>
    </div>
    </section>

    {/* 7. FOOTER CTA */}
    <section className="py-40 relative flex flex-col items-center justify-center text-center px-margin-mobile">
    <div className="absolute inset-0 flex items-center justify-center opacity-20 pointer-events-none -z-10">
    <div className="w-full h-[1px] bg-gradient-to-r from-transparent via-primary to-transparent"></div>
    </div>
    <div className="w-24 h-24 mb-12 opacity-80">
    <img alt="VoiceGuard Shield Logo" className="w-full h-full object-contain filter drop-shadow-[0_0_15px_rgba(0,242,255,0.5)]" src="/logo.png"/>
    </div>
    <h2 className="font-headline-lg text-headline-lg-mobile md:text-headline-lg text-on-surface mb-12 max-w-2xl tracking-tight">
                Protect your voice.<br/>
    <span className="text-on-surface-variant">Protect your organization.</span>
    </h2>
    <button className="bg-primary text-on-primary font-label-caps text-label-caps px-12 py-5 rounded-xl hover:bg-primary-container hover:shadow-[0_0_40px_rgba(0,219,231,0.5)] transition-all duration-300 uppercase tracking-widest text-[14px]">
                Deploy Now
            </button>
    <div className="mt-16 font-data-display text-[10px] text-on-surface-variant/40 tracking-widest uppercase">
                SECURE CONNECTION ESTABLISHED // E2E ENCRYPTED
            </div>
    </section>
    </div></main>
    <footer className="w-full bg-surface-container-lowest py-16"><div className="max-w-container-max mx-auto px-margin-desktop flex flex-col md:flex-row justify-between items-center gap-8"><div className="flex items-center gap-3"><img alt="VoiceGuard Logo" className="h-6 w-auto opacity-50 grayscale" src="/logo.png"/><span className="font-label-caps text-label-caps text-on-surface-variant">© 2026 VoiceGuard Security</span></div><div className="flex gap-8"><a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary" href="#">Privacy</a><a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary" href="#">Terms</a><a className="font-label-caps text-label-caps text-on-surface-variant hover:text-primary" href="#">Status</a></div></div></footer>
    </>
  );
}

export default LandingPage;
