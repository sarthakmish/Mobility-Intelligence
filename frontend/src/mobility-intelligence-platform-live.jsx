import { useState, useMemo, useRef, useEffect, useCallback } from "react";

/* ═══════════════════════════════════════════════════════════════
   MOBILITY SOLUTIONS INTELLIGENCE PLATFORM v3
   Live API-connected — Leadership-grade
   ═══════════════════════════════════════════════════════════════ */

// ── API CONFIGURATION ─────────────────────────────────────────
// Vite proxies /api → localhost:8001, so this works on any IP/hostname with no CORS.
const API_BASE = import.meta.env.VITE_API_URL ?? "";

// ── API → Dashboard data transformers ─────────────────────────
// The API returns {code, name, category, likelihood, impact, ...}
// The dashboard expects {id, cat, name, pos:{mar26:[L,I]}, rel, pil, ...}
const transformPestel = (apiFactors) => apiFactors.map(f => {
  // Format origin date as a human-readable string for the detail panel
  let originStr = "";
  if (f.origin_date) {
    try {
      const d = new Date(f.origin_date);
      originStr = d.toLocaleDateString("en-US", { month: "short", year: "numeric" });
    } catch(e){ originStr = ""; }
  }
  return {
    id: f.code,
    cat: f.category,
    name: f.name,
    desc: f.selection_reasoning || "",
    sr: (f.selection_reasoning || "").substring(0, 300),
    src: "Live API",
    st: f.trend === "new" ? "New" : f.trend === "escalating" ? "Escalating" : f.trend === "de-escalating" ? "De-escalating" : "Active",
    isNew: f.origin_date ? (Date.now() - new Date(f.origin_date).getTime()) < 90 * 86400000 : f.trend === "new",
    origin: originStr,                        // ← derived from origin_date
    originDate: f.origin_date || null,        // ← raw ISO for timeline plotting
    isFoundational: f.is_foundational || false,
    rel: typeof f.segment_relevance === "string" ? JSON.parse(f.segment_relevance) : (f.segment_relevance || {}),
    // ── REAL anchor points from pestel_score_history ──
    pos: {
      jan25: f.score_jan_2025 || null,        // [L, I] from history or null
      jan26: f.score_jan_2026 || null,        // [L, I] from history or null
      mar26: [f.likelihood, f.impact],         // current live snapshot
    },
    pil: typeof f.affected_pillars === "string" ? JSON.parse(f.affected_pillars) : (f.affected_pillars || []),
    segNote: {},
    _likelihood_reasoning: f.likelihood_reasoning,
    _impact_reasoning: f.impact_reasoning,
    _verification_verdict: f.verification_verdict,
    _verification_source: f.verification_source,
    // ── Freshness model ──
    freshnessTier: f.freshness_tier || "EMERGING",
    firstSeen: f.first_seen_date || null,
    lastConfirmed: f.last_confirmed_date || null,
    confirmationCount: f.confirmation_count || 1,
    _from_api: true,
    _last_refreshed: f.last_refreshed,
  };
});

const transformTechs = (apiTechs) => apiTechs.map(t => ({
  n: t.name,
  p: t.pillar,
  mat: t.maturity ? t.maturity.charAt(0).toUpperCase() + t.maturity.slice(1) : "Growth",
  inc: t.includes || "",
  sz: typeof t.market_data === "string" ? JSON.parse(t.market_data) : (t.market_data || {}),
  cagr: t.cagr || 0,
  conf: (t.confidence || "medium").charAt(0).toUpperCase(),
  src: t.source_note || t.analysis_reasoning?.substring(0, 80) || "API",
  source_note: t.source_note || "",
  _code: t.code,
  _from_api: true,
}));

const getSourceConfidence = (src, conf) => {
  const s = (src || "").toLowerCase();
  // ── Priority 1: honour explicit prefixes set by the audit ──
  // DB source_note now starts with "Published:", "Derived from", or "AI Estimate;"
  if (s.startsWith("published:")) {
    const label = src.replace(/^Published:\s*/i, "").split(" Report")[0].split(" India")[0];
    return {label, bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  }
  if (s.startsWith("derived from")) {
    const label = "Derived · " + src.replace(/^Derived from\s*/i, "").split(" ").slice(0,3).join(" ");
    return {label, bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  }
  if (s.includes("ai estimate") || s.startsWith("ai estimate")) {
    return {label:"AI Estimate", bg:"#ef444415", color:"#ef4444", border:"#ef444430", tier:"estimate"};
  }
  // ── Priority 2: fallback heuristics for hardcoded fallback data ──
  if (!src || src === "API") {
    if (conf === "H") return {label:"Published", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
    if (conf === "M") return {label:"Market research", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
    return {label:"Estimate", bg:"#ef444415", color:"#ef4444", border:"#ef444430", tier:"estimate"};
  }
  if (s.includes("acma")) return {label:"ACMA FY25", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("siam")) return {label:"SIAM FY25", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("mordor")) return {label:"Mordor Intelligence", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("imarc")) return {label:"IMARC Group", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("ibef")) return {label:"IBEF", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("ps market")) return {label:"PS Market Research", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("indexbox")) return {label:"IndexBox", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("vahan") || s.includes("icra")) return {label:"ICRA/Vahan", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("mandate") || s.includes("bs-vi") || s.includes("regulatory")) return {label:"Regulatory", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (s.includes("crisil")) return {label:"CRISIL Research", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("frost")) return {label:"Frost & Sullivan", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("marketsandmarkets")) return {label:"MarketsandMarkets", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("grand view")) return {label:"Grand View Research", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("allied")) return {label:"Allied Market Research", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("bloombergnef")||s.includes("bnef")) return {label:"BloombergNEF", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("mckinsey")) return {label:"McKinsey & Co", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("industry")||s.includes("pwc")||s.includes("bosch")) return {label:"Industry est.", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  if (s.includes("[est.]")||s.includes("est.")||s.includes("estimate")) return {label:"Estimate", bg:"#ef444415", color:"#ef4444", border:"#ef444430", tier:"estimate"};
  if (conf==="H") return {label:"Published", bg:"#22c55e15", color:"#22c55e", border:"#22c55e30", tier:"published"};
  if (conf==="M") return {label:"Market research", bg:"#f9731615", color:"#f97316", border:"#f9731630", tier:"derived"};
  return {label:"Estimate", bg:"#ef444415", color:"#ef4444", border:"#ef444430", tier:"estimate"};
};

const SEGS={"4W_PV":{l:"4W Passenger Vehicle",s:"4W PV",u:"43.0L FY25",ic:"🚗",src:"SIAM Verified"},"LCV":{l:"Light Commercial (≤7.5T)",s:"LCV",u:"5.2L FY25",ic:"🚐",src:"SIAM Verified"},"HCV":{l:"Heavy Commercial (>7.5T)",s:"HCV",u:"4.4L FY25",ic:"🚛",src:"SIAM Verified"},"2W":{l:"Two Wheeler",s:"2W",u:"1.96Cr FY25",ic:"🏍️",src:"SIAM Verified"},"3W":{l:"Three Wheeler",s:"3W",u:"7.41L FY25",ic:"🛺",src:"SIAM Verified"},"Tractor":{l:"Tractor",s:"Tractor",u:"10.6L CY25",ic:"🚜",src:"IBEF Verified"}};
const CAT={P:{l:"Political",c:"#ef4444"},E:{l:"Economic",c:"#f97316"},S:{l:"Social",c:"#a855f7"},T:{l:"Technological",c:"#3b82f6"},En:{l:"Environmental",c:"#22c55e"},L:{l:"Legal",c:"#6366f1"}};
const MC={Emerging:"#f97316",Growth:"#22c55e",Mature:"#3b82f6",Declining:"#94a3b8"};
// Currency formatting — EUR rate April 2026
const EUR_RATE=106.5;

// ── Single source of truth for pillar colors ──
// Used by: PILLARS array, V3 bubble border, V3 legend, V4 strip border.
const PILLAR_COLORS = {
  "ADAS":           "#dc2626",
  "Motion":         "#2563eb",
  "Energy":         "#16a34a",
  "Body & Comfort": "#9333ea",
  "Infotainment":   "#ca8a04",
  "OS":             "#0891b2",
  "Compute":        "#7c3aed",
  "ECUs":           "#8b5cf6",
  "Semiconductors": "#6d28d9",
  "Actuators":      "#475569",
  "Solutions":      "#64748b",
  "Services":       "#0ea5e9",
  "Cloud":          "#0284c7",
};
// Category weights for Top N ranking — regulatory mandates outrank OEM-specific economic news
const CATEGORY_WEIGHTS={"P":1.25,"L":1.25,"T":1.1,"En":1.0,"E":0.85,"S":0.8};
// ══ MASTER FILTER DATA — single source of truth for all segment filtering ══
const OEM_SEGMENTS={
  "jlr":["4W_PV"],"jaguar":["4W_PV"],"land rover":["4W_PV"],
  "range rover":["4W_PV"],"bmw":["4W_PV"],"mercedes":["4W_PV"],
  "audi":["4W_PV"],"volvo cars":["4W_PV"],"porsche":["4W_PV"],
  "mg motor":["4W_PV"],"kia":["4W_PV"],"skoda":["4W_PV"],
  "volkswagen":["4W_PV"],"citroen":["4W_PV"],"vinfast":["4W_PV"],
  "genesis":["4W_PV"],"lexus":["4W_PV"],"jsw motors":["4W_PV"],
  "byd":["4W_PV"],"honda '0 alpha'":["4W_PV"],"honda 0 alpha":["4W_PV"],
  "tata motors":["4W_PV","LCV","HCV"],
  "maruti":["4W_PV","LCV"],"hyundai":["4W_PV"],
  "toyota":["4W_PV","LCV","HCV"],"mahindra":["4W_PV","LCV","HCV","Tractor"],
  "renault":["4W_PV"],"nissan":["4W_PV"],
  "hero motocorp":["2W"],"bajaj":["2W","3W"],"tvs motor":["2W"],
  "royal enfield":["2W"],"ola electric":["2W"],
  "ather":["2W"],"suzuki motorcycle":["2W"],"honda motorcycle":["2W"],"yamaha":["2W"],
  "ashok leyland":["LCV","HCV"],"eicher":["LCV","HCV"],
  "bharat benz":["HCV"],"daimler":["HCV"],
  "force motors":["LCV"],"euler motors":["LCV"],"piaggio":["3W","LCV"],
  "atul auto":["3W"],
  "sonalika":["Tractor"],"escorts":["Tractor"],"swaraj":["Tractor"],
  "john deere":["Tractor"],"kubota":["Tractor"],"tafe":["Tractor"],
};
const TOPIC_SEGMENTS={
  // Regulatory/Policy
  "cafe iii":["4W_PV","LCV"],"cafe phase":["4W_PV","LCV"],
  "corporate average fuel":["4W_PV","LCV"],
  "gati shakti":["LCV","HCV"],
  "trem v":["Tractor"],"trem ":["Tractor"],
  "aebs mandatory":["HCV"],"aebs for":["HCV"],
  "aeb mandatory":["4W_PV"],
  "euro 7":["4W_PV","LCV","HCV"],"euro7":["4W_PV","LCV","HCV"],
  "bharat ncap":["4W_PV"],"bncap":["4W_PV"],
  "scrappage policy":["4W_PV","LCV","HCV"],"vehicle scrappage":["4W_PV","LCV","HCV"],
  "obd-ii":["2W","3W"],
  // Ethanol — specific to avoid matching generic text
  "ethanol blending e20":["4W_PV","2W","LCV"],
  "ethanol blending prog":["4W_PV","2W","LCV"],
  "e20 mandate":["4W_PV","2W","LCV"],
  "ethanol blending":["4W_PV","2W","LCV"],
  "flex-fuel":["4W_PV","2W"],
  // Segment-specific technology/market topics
  "cv financing":["LCV","HCV"],
  "e-bus":["HCV"],"ebus":["HCV"],"etruck":["HCV"],
  "bus localisation":["HCV"],"truck localisation":["HCV","LCV"],
  "e-bus/truck":["HCV"],
  "cbam":["HCV","LCV"],"eu cbam":["HCV","LCV"],
  "connected car":["4W_PV"],
  "software-defined vehicle":["4W_PV"],"sdv ":["4W_PV"],
  "hydrogen fuel cell":["HCV"],"hydrogen ice":["HCV"],
  "agri mechanisation":["Tractor"],"precision farming":["Tractor"],
  "gig economy":["3W"],
  // SUV/PV topics — block leakage into 2W/3W/Tractor
  "suv platform":["4W_PV"],"suv expansion":["4W_PV"],
  "suv proliferation":["4W_PV"],"suv push":["4W_PV"],
  "suv segment":["4W_PV"],"multi-oem suv":["4W_PV"],
  "multi oem suv":["4W_PV"],
  "multi-oem ev platform":["4W_PV"],"multi oem ev platform":["4W_PV"],
  "pv demand":["4W_PV"],"pv market":["4W_PV"],"pv sales":["4W_PV"],
  "pv sub-":["4W_PV"],"pv volume":["4W_PV"],"record pv":["4W_PV"],
  "india pv":["4W_PV"],"small car":["4W_PV"],
  "premiumisation":["4W_PV"],"premiumization":["4W_PV"],
  // ADAS — L3 and above is 4W/HCV only
  "l3 radar":["4W_PV","HCV"],"l3 adas":["4W_PV","HCV"],
  "lidar ecosystem":["4W_PV","HCV"],"adas l3":["4W_PV","HCV"],
  // Misc
  "lightweighting":["4W_PV","LCV"],
  "product liability":["4W_PV"],
  "dpdp act":["4W_PV"],
};
const TECH_EXCLUSIONS={
  "Tractor":[
    "adas","camera system","lidar","radar sensor","lane keep",
    "blind spot","parking assist","surround view","traffic sign",
    "adaptive cruise","driver monitor","cabin camera",
    "infotainment","hmi","v2x","5g auto","smart grid","v2g",
    "dc fast charg","battery swap","wireless induct","ev hub motor",
    "2w/3w","air disc","over-the-air","ota","cloud platform",
    "cobots","additive manuf","vehicle os","cybersecurity",
    "e-axle","ev traction","ev battery management","ev dc-dc",
    "ev high-voltage","48v mild hybrid","heavy-duty ev","hydrogen","fuel cell",
  ],
  "3W":[
    "common rail diesel","gasoline direct","turbo",
    "lidar","l3+","surround view","parking assist",
    "adaptive cruise","lane keep","blind spot","traffic sign",
    "driver monitor","cabin camera","air disc brake",
    "heavy-duty","hydrogen","fuel cell","smart grid","v2g",
    "wireless induct","vehicle os","cloud platform",
    "cobots","additive manuf","48v mild hybrid",
  ],
  "2W":[
    "common rail diesel","gasoline direct injection",
    "lidar","l3+","surround view","parking assist",
    "adaptive cruise","lane keep","blind spot","traffic sign",
    "air disc brake","heavy-duty","hydrogen","fuel cell",
    "smart grid","v2g","wireless induct",
    "in-vehicle infotainment","hmi","cobots","additive manuf",
    "48v mild hybrid",
  ],
  "4W_PV":["2w/3w","battery swapping","ev hub motor","heavy-duty ev","etruck","ebus"],
  "LCV":["2w/3w","ev hub motor","battery swapping"],
  "HCV":["2w/3w","ev hub motor","battery swapping"],
};
let _curr="INR";
let _liveEurRate=EUR_RATE;
const fmt=(n,_c)=>{const c=_c||_curr;if(n===undefined||n===null||n===""||n===0)return"—";
  if(c==="EUR"){const e=n*10/_liveEurRate;// ₹Cr → €M: 1 Cr = 10M INR
    if(e>=1000)return`€${(e/1000).toFixed(1)}B`;if(e>=1)return`€${e.toFixed(0)}M`;return`€${e.toFixed(1)}M`;}
  if(n>=100000)return`₹${(n/100000).toFixed(1)}L Cr`;if(n>=1000)return`₹${(n/1000).toFixed(1)}K Cr`;return`₹${Math.round(n)} Cr`;
};

const FALLBACK_PESTEL=[
{id:"pli",cat:"P",name:"PLI Scheme ₹25,938 Cr",desc:"Production Linked Incentive — ₹35,657 Cr invested, ₹2,322 Cr disbursed as of Jan 2026. Covers advanced automotive technology, ACC battery cells, and auto components.",src:"IBEF Jan 2026",st:"Active",isNew:false,origin:"Sep 2021 — GoI notified PLI for auto & ACC battery",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"H","3W":"M","Tractor":"M"},pos:{jan25:[7.5,8],jan26:[8.5,8.5],mar26:[8.5,8.5]},pil:["Energy","Motion","Semiconductors"],segNote:{"4W_PV":"Direct incentive for EV components, battery cells. Bosch, Continental among approved applicants. ₹35,657 Cr invested creating 50+ component manufacturing facilities.","2W":"Significant for EV 2W powertrain localization. Ather, Ola benefit from component PLI for motors, controllers.","HCV":"PLI covers advanced powertrain, fuel cell components for HCV segment.","Tractor":"Limited direct applicability; component PLI covers engine parts and transmission."}},
{id:"fame3",cat:"P",name:"PM E-Drive",desc:"Demand-side EV subsidy — e-2W, e-3W, e-bus, e-4W and charging infra. ₹10,900 Cr outlay 2024-2027.",src:"MoHI 2024",st:"Active",isNew:false,origin:"Mar 2015 — FAME I launched; Oct 2024 PM E-Drive replaced FAME II",rel:{"4W_PV":"H","LCV":"M","HCV":"H","2W":"H","3W":"H","Tractor":"M"},pos:{jan25:[7,7.5],jan26:[8,8],mar26:[8,8]},pil:["Energy","Motion","Solutions"],segNote:{"4W_PV":"Subsidizes battery pack cost, making EVs ₹1.5-2L cheaper. 14,000+ e-4W subsidized.","2W":"₹5,000/kWh subsidy critical for Ola/Ather/TVS price competitiveness. 1.1M e-2W subsidized.","3W":"₹10,000/kWh subsidy making e-3W cheaper than CNG. >50% share in cities.","HCV":"e-bus subsidies driving adoption in 10+ cities. 7,500+ e-buses ordered under PM E-Drive."}},
{id:"make",cat:"P",name:"Make in India / Atmanirbhar",desc:"Localization push — rare earth magnet incentive tripled to $788M. Trade surplus $453M FY25.",src:"ACMA FY25",st:"Active",isNew:false,origin:"Sep 2014 — Make in India launched; May 2020 Atmanirbhar Bharat",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"M","3W":"M","Tractor":"H"},pos:{jan25:[8,7],jan26:[8,7.5],mar26:[8.5,7.5]},pil:["Semiconductors","ECUs","Actuators"],segNote:{"4W_PV":"Tata, Mahindra expanding local EV supply chains. 70%+ localization target. Import substitution saving $2B+/yr.","HCV":"CV components heavily localized — 85%+. Focus on electronics content increase from current 15% to 25%.","Tractor":"95%+ localized already. Atmanirbhar pushing remaining electronics imports — ECUs, precision sensors.","LCV":"LCV component localization rising rapidly. Wiring harness, braking systems now 90%+ local."}},
{id:"gst",cat:"P",name:"GST 2.0 Rate Reform",desc:"GST cuts on hybrids (28%→18%) & auto parts. All segments double-digit growth Nov-Dec 2025.",src:"SIAM Dec 2025",st:"Active",isNew:true,origin:"Jul 2025 — GST Council approved hybrid vehicle rate cut",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"H","3W":"H","Tractor":"M"},pos:{jan25:null,jan26:[7,7],mar26:[8,7.5]},pil:["Motion","Body & Comfort","Infotainment"],segNote:{"4W_PV":"Hybrid GST cut boosting Maruti, Toyota hybrid sales +40%. Component demand surge across powertrain.","2W":"Lower GST on spare parts boosting aftermarket. EV 2W component GST at 5%.","HCV":"Input tax credit improvements for fleet operators. Leasing GST rationalization helping.","LCV":"Component replacement parts GST simplified — single 18% rate for most items."}},
{id:"tariff",cat:"E",name:"US Tariffs (50%→18%)",desc:"Initially 25-50% on auto components ($6.6B at risk). Reduced to 18% Feb 2026. ICRA: 8% of production impacted.",src:"ICRA Sep 2025 · BS Feb 2026",st:"De-escalating",isNew:true,origin:"Apr 2025 — US imposed 25-50% tariffs; Feb 2026 reduced to 18%",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"M","3W":"L","Tractor":"M"},pos:{jan25:null,jan26:[8.5,9],mar26:[6,7]},pil:["Motion","Body & Comfort","Energy"],segNote:{"4W_PV":"Drivetrain, braking, body components heavily exported. 18% manageable vs. initial 50%. $3.2B 4W component exports to US.","HCV":"CV component exports to US significant — brake assemblies, axle components. $800M affected.","LCV":"LCV component exports smaller but growing. Steering, suspension systems targeted.","Tractor":"Tractor component exports to US ~$200M. 18% tariff absorbed through cost engineering."}},
{id:"suv",cat:"E",name:"SUV Boom & Premiumization",desc:"UV share 66% of PV. Record 44.89L CY2025 (+5%). Electronics content per SUV 2-3x vs. hatchback.",src:"SIAM CY2025",st:"Accelerating",isNew:false,origin:"2017 — UV overtook cars in volume; structural shift since Creta launch 2015",rel:{"4W_PV":"H","LCV":"L","HCV":"L","2W":"L","3W":"L","Tractor":"L"},pos:{jan25:[8,7.5],jan26:[8.5,8],mar26:[9,8]},pil:["Infotainment","Body & Comfort","ADAS"],segNote:{"4W_PV":"Driving ADAS adoption, premium infotainment (₹15K→₹45K per car), panoramic sunroofs, 6-airbag standard. Electronics content jumps from ₹35K to ₹1.2L per vehicle."}},
{id:"ev",cat:"E",name:"EV Cost Parity Approaching",desc:"EV 4W +77% YoY. 2W EV 7.4% penetration. Total 2.3M EVs CY2025, 8% share.",src:"Vahan Dec 2025 · IBEF",st:"Accelerating",isNew:false,origin:"2019 — first mass-market EVs (Nexon EV, Ather 450); inflection in 2023",rel:{"4W_PV":"H","LCV":"M","HCV":"L","2W":"H","3W":"H","Tractor":"L"},pos:{jan25:[6,8],jan26:[7,8.5],mar26:[7.5,8.5]},pil:["Energy","Motion","Compute","Cloud"],segNote:{"4W_PV":"Battery cost at $120/kWh approaching ICE parity. 1.76L e-4W in CY2025 (+77%). Tata 65% share.","2W":"Ola S1 Air at ₹69,999 — cheaper than many ICE scooters. 7.4% penetration and rising.","3W":"Fastest EV transition globally. >50% e-3W in Delhi, Bangalore. Battery swap enabling 24/7 operation."}},
{id:"rare",cat:"E",name:"China Rare Earth Controls",desc:"India imported $221M magnets FY25, 80%+ from China. Govt tripled domestic incentive to $788M. Alternative sourcing progressing.",src:"Autocar Pro Nov 2025",st:"De-escalating",isNew:true,origin:"Oct 2023 — China restricted gallium/germanium; Dec 2024 expanded to rare earth magnets",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"H","3W":"M","Tractor":"L"},pos:{jan25:null,jan26:[7,8.5],mar26:[6,7]},pil:["Energy","Actuators","Semiconductors"],segNote:{"4W_PV":"EV motor magnets still 80% China-sourced but $788M incentive accelerating domestic processing. Tata, M&M securing Australia/Vietnam supply.","2W":"Hub motors in e-2W use permanent magnets. Ola/Ather diversifying to ferrite-based motors for low-cost models.","HCV":"Limited direct impact — HCV electrification slow. Starter motors, alternators still need magnets.","LCV":"LCV EPS motors affected. Alternative ferrite motor designs being validated by Bosch, Mando."}},
{id:"geo",cat:"E",name:"Geopolitical / Red Sea",desc:"US-Iran-Israel conflict intensifying. Red Sea shipping disrupted — freight costs +200%, 4-8 week delays. Semiconductor supply chains strained.",src:"Industry 2024-26",st:"Escalating",isNew:true,origin:"Nov 2023 — Houthi attacks on Red Sea; escalated with Iran-Israel conflict 2024-25",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"M","3W":"L","Tractor":"M"},pos:{jan25:[6.5,7],jan26:[7,8],mar26:[8,8.5]},pil:["Semiconductors","Energy","Motion"],segNote:{"4W_PV":"Semiconductor supply delays affecting ECU, infotainment production. 4-8 week lead time increase. Shipping cost for European imports +200%. OEMs building 6-8 week buffer inventory.","HCV":"Specialized chips for BS-VI emission control facing 6-10 week delays. Aftertreatment component imports from Europe disrupted. ₹8-12K cost increase per truck.","LCV":"Electronics content rising — supply chain disruption hitting new model launches. Component cost inflation 3-5%.","Tractor":"Tractor electronics imports limited but hydraulic component supply from Europe affected. ₹2-4K cost increase."}},
{id:"safe",cat:"S",name:"Road Safety Consciousness",desc:"1.73L deaths/yr. ADAS from ₹8.32L vehicles. Consumer willingness to pay for safety features rising sharply.",src:"MoRTH · CarBike360",st:"Growing",isNew:false,origin:"2014 — India signed UN Decade of Action for Road Safety; Bharat NCAP 2023",rel:{"4W_PV":"H","LCV":"M","HCV":"H","2W":"H","3W":"M","Tractor":"M"},pos:{jan25:[7,7.5],jan26:[7.5,8],mar26:[8,8]},pil:["ADAS","Infotainment","Actuators"],segNote:{"4W_PV":"NCAP ratings becoming purchase criteria. 5-star expected in ₹10L+. 6 airbags mandatory from Oct 2025.","HCV":"40% HCV accidents fatigue-related. DMS and AEBS mandate addresses this. Insurance discount for safety.","2W":"2W account for 44% road deaths. ABS mandatory, traction control spreading. CBS standard on commuters.","Tractor":"ROPS (rollover protection) increasingly adopted. Operator safety awareness growing."}},
{id:"conn",cat:"S",name:"Connected Generation",desc:"Android Auto/CarPlay non-negotiable. TFT clusters standard. OTA updates expected.",src:"Industry consensus",st:"Dominant",isNew:false,origin:"2018 — Hyundai Venue first connected car India; now standard across segments",rel:{"4W_PV":"H","LCV":"L","HCV":"L","2W":"H","3W":"L","Tractor":"L"},pos:{jan25:[8.5,6.5],jan26:[9,7],mar26:[9,7]},pil:["Infotainment","Cloud","Services","OS"],segNote:{"4W_PV":"10\"+ touchscreens standard even in ₹6L cars. Connected features drive 15-20% premiumization willingness.","2W":"Ather Halo, TVS SmartXConnect creating premium connected 2W experience. TFT clusters now in ₹1.5L+ bikes."}},
{id:"rural",cat:"S",name:"Rural Demand Revival",desc:"Above-normal monsoon. 2W +9% FY25. Tractors 1.06M CY25. Rural EV accelerating via subsidy stacking.",src:"SIAM · DD News",st:"Active",isNew:false,origin:"FY24 — monsoon normalization after 2 weak years; rural credit expansion",rel:{"4W_PV":"M","LCV":"M","HCV":"L","2W":"H","3W":"H","Tractor":"H"},pos:{jan25:[6,6],jan26:[7.5,6.5],mar26:[7.5,6.5]},pil:["Motion","Body & Comfort"],segNote:{"2W":"Entry-level 100-125cc drive rural volume. EV 2W entering via PM E-Drive + state subsidies stacking.","3W":"Rural last-mile connectivity expanding. E-3W replacing diesel autos in semi-urban areas.","Tractor":"Record 1.06M units CY25. Good monsoon + MSP hikes + PM-KISAN driving purchasing power.","4W_PV":"Entry-level PV demand recovering. Alto, WagonR volumes up 8% in rural markets."}},
{id:"sic",cat:"T",name:"SiC Semiconductor Revolution",desc:"SiC replacing IGBT for 800V EV. 30% efficiency gain. RIR Power first India SiC fab (Odisha).",src:"IndexBox · RIR",st:"Accelerating",isNew:false,origin:"2022 — global 800V EV wave; RIR Odisha fab announced 2024",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"M","3W":"L","Tractor":"L"},pos:{jan25:[5.5,7.5],jan26:[6.5,8],mar26:[7,8.5]},pil:["Semiconductors","Energy","Compute"],segNote:{"4W_PV":"Tata Avinya, Mahindra XEV 9e moving to 800V SiC inverters. 30% more range. India SiC market ₹900 Cr.","2W":"Low-voltage 2W don't need SiC yet, but high-performance e-2W (Ultraviolette F77) exploring it.","HCV":"SiC for e-bus inverters. Higher efficiency critical for 300+ km range."}},
{id:"sdv",cat:"T",name:"Software-Defined Vehicle",desc:"Central compute replacing 70+ ECUs. Zonal architecture. Feature-on-demand via OTA.",src:"Bosch · Industry",st:"Emerging",isNew:false,origin:"2020 — Tesla model; India OEMs adopted zonal concepts from 2023",rel:{"4W_PV":"H","LCV":"L","HCV":"M","2W":"M","3W":"L","Tractor":"L"},pos:{jan25:[4,8],jan26:[5,8.5],mar26:[5.5,8.5]},pil:["Compute","OS","Cloud","ECUs","ADAS"],segNote:{"4W_PV":"Tata, M&M investing in zonal architecture. Central compute enables OTA feature upgrades. ₹2K Cr addressable.","HCV":"Fleet management integration driving SDV adoption for predictive maintenance — 30% downtime reduction."}},
{id:"l2",cat:"T",name:"L2+ Autonomy Mainstream",desc:"Mahindra L2 in Scorpio-N, XUV700. MoRTH mandatory AEBS for >8 pax from Apr 2026.",src:"Mordor Jan 2026",st:"Active",isNew:false,origin:"2021 — MG Gloster first L1 ADAS in India; L2 from Mahindra 2022",rel:{"4W_PV":"H","LCV":"L","HCV":"H","2W":"L","3W":"L","Tractor":"L"},pos:{jan25:[5,7],jan26:[6.5,7.5],mar26:[7,8]},pil:["ADAS","Actuators","ECUs","Semiconductors"],segNote:{"4W_PV":"L2 now in ₹15L+ vehicles (XUV700, Scorpio-N, Safari). BNCAP 2.0 (2027) will drive to ₹10L segment. India ADAS market $1.15B→$3.12B by 2031.","HCV":"AEBS/DDAWS mandate for buses >8 pax Apr 2026. Fleet operators demanding for insurance premium reduction (12-15% discount)."}},
{id:"ai",cat:"T",name:"AI & IoT in Vehicles",desc:"Tata Harrier.ev connected AI. Predictive maintenance, intelligent charging, voice assistants.",src:"IBEF · MarkNtel",st:"Growing",isNew:true,origin:"2024 — Tata Harrier.ev AI launch; Hyundai connected car AI 2025",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"H","3W":"L","Tractor":"M"},pos:{jan25:null,jan26:[5,6.5],mar26:[6,7]},pil:["Cloud","Services","Solutions","Infotainment"],segNote:{"4W_PV":"AI voice assistants, predictive maintenance, smart charging optimization. Over-the-air personalization.","2W":"Ather Halo AI ride analysis, TVS iQube diagnostics. Navigation + riding mode AI.","Tractor":"Precision agriculture AI — yield prediction, soil analysis, auto-steering GPS."}},
{id:"bs6",cat:"En",name:"BS-VI Stage 2 Emissions",desc:"DPF, SCR, precision injection mandatory. RDE testing. ICE cost +8-15%.",src:"MoRTH 2025-26",st:"Implementing",isNew:false,origin:"Apr 2020 — BS-VI Stage 1; Apr 2023 BS-VI Stage 2 (RDE for passenger vehicles)",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"H","3W":"M","Tractor":"H"},pos:{jan25:[9,7],jan26:[9.5,7.5],mar26:[9.5,7.5]},pil:["Energy","Actuators","Infotainment"],segNote:{"4W_PV":"GDI, turbo, DPF/GPF mandatory. ₹15-25K cost increase per vehicle. Precision sensors market ₹10.5K Cr.","HCV":"SCR + DPF + EGR full aftertreatment. ₹1-1.5L cost per truck. Urea infrastructure scaling.","2W":"OBD-II + tighter NOx/HC. Fuel injection replacing carburetors across all models. ₹3K cost increase.","Tractor":"TREM V (separate regulation) but BS-VI principles apply to on-road tractors."}},
{id:"nz",cat:"En",name:"Net Zero 2070 Target",desc:"30% EV by 2030. Carbon -45% by 2030. Green hydrogen for HCV.",src:"GoI COP26",st:"Long-term",isNew:false,origin:"Nov 2021 — PM Modi COP26 Glasgow commitment; NDC updated 2023",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"H","3W":"H","Tractor":"M"},pos:{jan25:[5,7],jan26:[5.5,7.5],mar26:[6,7.5]},pil:["Energy","Motion","Solutions"],segNote:{"4W_PV":"30% EV target creating massive xEV powertrain opportunity. Estimated ₹3L Cr component market by 2030.","HCV":"Green hydrogen fuel cell for long-haul. NTPC, Indian Oil pilots underway. ₹800 Cr Green Hydrogen Mission."}},
{id:"lw",cat:"En",name:"Lightweighting for Range",desc:"Aluminum/composites replacing steel. Multi-material BIW. Weight -10-15% per generation.",src:"Industry",st:"Growing",isNew:false,origin:"2018 — global EV range anxiety drove lightweighting; India adopted 2021+",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"M","3W":"L","Tractor":"L"},pos:{jan25:[5.5,6],jan26:[6,6.5],mar26:[6.5,6.5]},pil:["Body & Comfort"],segNote:{"4W_PV":"EV platforms using aluminum-intensive BIW. 100kg saving = 10km range. Tata Avinya multi-material.","HCV":"High-strength steel reducing chassis weight. 500kg saving possible. Fuel saving 3-5%."}},
{id:"bncap",cat:"L",name:"Bharat NCAP Safety",desc:"Star ratings mandatory. BNCAP 2.0 (2027) includes ADAS. AEB for 5-star.",src:"Mordor Jan 2026 · ARAI",st:"Active",isNew:false,origin:"Aug 2023 — Bharat NCAP launched by MoRTH; first tests Tata Harrier 5★",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"L","3W":"L","Tractor":"L"},pos:{jan25:[8,8.5],jan26:[8.5,9],mar26:[9,9]},pil:["ADAS","Body & Comfort","Infotainment","Actuators"],segNote:{"4W_PV":"5-star becoming marketing essential. Honda Amaze 2026 first sub-₹9L with AEB. 15+ models tested, 8 achieved 5★.","LCV":"Commercial vehicle BNCAP assessment framework under development.","HCV":"Bus safety assessment criteria being drafted with ARAI."}},
{id:"a189",cat:"L",name:"AIS-189 Cybersecurity",desc:"Mandatory secure OTA, intrusion detection, ECU security. UNECE WP.29 aligned.",src:"ARAI",st:"Upcoming",isNew:true,origin:"2024 — ARAI drafted AIS-189; type approval from 2026 for new models",rel:{"4W_PV":"H","LCV":"M","HCV":"M","2W":"M","3W":"L","Tractor":"L"},pos:{jan25:null,jan26:[5,6],mar26:[6,6.5]},pil:["Cloud","ECUs","OS","Infotainment"],segNote:{"4W_PV":"All connected vehicles need cybersecurity type-approval. Estimated ₹5-8K per vehicle compliance cost.","2W":"Connected 2W (Ather, Ola) need compliance for OTA update security."}},
{id:"a140",cat:"L",name:"AIS-140 GPS Tracking",desc:"Mandatory GPS + emergency for public transport vehicles. 12+ states enforcing.",src:"MoRTH",st:"Active",isNew:false,origin:"Apr 2018 — MoRTH mandated AIS-140 for all public transport",rel:{"4W_PV":"L","LCV":"M","HCV":"H","2W":"L","3W":"H","Tractor":"L"},pos:{jan25:[8.5,5.5],jan26:[9,6],mar26:[9,6]},pil:["Infotainment","Services"],segNote:{"HCV":"All inter-state buses mandated. 85%+ fleet compliance. GPS + SOS creating ₹500 Cr+ installed base.","3W":"Autos in 12+ states mandated. Low-cost GPS + SOS creating ₹200 Cr market. Enforcement tightening."}},
{id:"aebs",cat:"L",name:"Mandatory AEBS (Buses/Trucks)",desc:"MoRTH: mandatory AEB, DDAWS, LDWS for vehicles >8 passengers from Apr 2026.",src:"MoRTH Mar 2025",st:"Proposed",isNew:true,origin:"Mar 2025 — MoRTH draft notification; Apr 2026 implementation",rel:{"4W_PV":"L","LCV":"M","HCV":"H","2W":"L","3W":"L","Tractor":"L"},pos:{jan25:null,jan26:[6,7.5],mar26:[7,8]},pil:["ADAS","Actuators","ECUs"],segNote:{"HCV":"Every new bus/truck >8 pax needs AEB, DMS, LDWS from Apr 2026. ₹50-80K additional per vehicle. 2L+ vehicles/yr affected.","LCV":"Large vans (>8 pax) included — Tempo Traveller, Force Traveller. ~80K units/yr."}},
{id:"tremV",cat:"En",name:"TREM V Emission Norms",desc:"DPF, SCR, EGR mandatory for new tractors from 2026. ₹40-80K cost increase on ₹5-8L machines.",src:"MoEFCC · TMA 2025",st:"Implementing",isNew:true,origin:"2024 — MoEFCC finalized TREM V; Apr 2026 for new models",rel:{"4W_PV":"L","LCV":"L","HCV":"L","2W":"L","3W":"L","Tractor":"H"},pos:{jan25:null,jan26:[7,8],mar26:[8.5,9]},pil:["Energy","Actuators","Infotainment"],segNote:{"Tractor":"Biggest regulatory change in a decade. DEF infra needed in rural areas. ₹40-80K cost increase on ₹5-8L machines. M&M, TAFE, Sonalika scrambling to comply."}},
{id:"tractElec",cat:"T",name:"Tractor Electrification & Precision Ag",desc:"Sonalika Tiger Electric, Escorts e-tractor. GPS auto-steering, yield mapping.",src:"IBEF · Sonalika 2025",st:"Emerging",isNew:true,origin:"2023 — Sonalika Tiger Electric launched; Escorts pilot 2024",rel:{"4W_PV":"L","LCV":"L","HCV":"L","2W":"L","3W":"L","Tractor":"H"},pos:{jan25:null,jan26:[4.5,7],mar26:[5.5,7.5]},pil:["Motion","Energy","Infotainment","Semiconductors"],segNote:{"Tractor":"Early stage but transformative. 4-6hr range sufficient for small farms. 5x electronics content vs ICE tractor. GPS auto-steer saving 15% fuel/time."}},
{id:"obd2w",cat:"L",name:"OBD-II Mandate for 2W",desc:"OBD Stage II mandatory for all 2W from Apr 2025. Electronics content 3x increase.",src:"MoRTH Apr 2025",st:"Active",isNew:true,origin:"Apr 2025 — OBD-II mandate effective for all new 2W models",rel:{"4W_PV":"L","LCV":"L","HCV":"L","2W":"H","3W":"M","Tractor":"L"},pos:{jan25:[6,7],jan26:[8,7.5],mar26:[8.5,8]},pil:["Infotainment","ECUs","Semiconductors"],segNote:{"2W":"Game-changer. Every new 2W needs OBD-II ECU + O2 sensor + catalyst monitor. ₹3,000 Cr+ market from near-zero. 2Cr units/yr affected.","3W":"OBD requirements less stringent but still driving electronics content. 7.4L units/yr affected."}},
{id:"ev2w",cat:"E",name:"Electric 2W Price War",desc:"Ola S1 Air at ₹69,999. Battery swapping by Gogoro/Hero at scale. 7.4% penetration.",src:"Vahan Dec 2025 · ET Auto",st:"Accelerating",isNew:false,origin:"2020 — Ather 450 commercial launch; price war from 2023 with Ola S1 Air",rel:{"4W_PV":"L","LCV":"L","HCV":"L","2W":"H","3W":"M","Tractor":"L"},pos:{jan25:[6.5,7.5],jan26:[8,8],mar26:[8.5,8.5]},pil:["Energy","Motion","Solutions"],segNote:{"2W":"S1 Air cheaper than Honda Activa 125. BaaS by Gogoro-Hero removes range anxiety. 15% penetration projected by 2027.","3W":"E-3W benefiting from 2W battery cost reductions — shared cell chemistry."}},
{id:"cvreg",cat:"L",name:"Axle Load Norms & Scrappage",desc:"Revised axle load + 15-year mandatory scrappage. 11L+ trucks eligible for scrappage. Green tax.",src:"MoRTH · SIAM",st:"Active",isNew:false,origin:"2018 — revised axle load norms; 2021 Vehicle Scrappage Policy launched",rel:{"4W_PV":"L","LCV":"H","HCV":"H","2W":"L","3W":"L","Tractor":"L"},pos:{jan25:[7.5,7],jan26:[8,7.5],mar26:[8.5,8]},pil:["Motion","Body & Comfort","Infotainment"],segNote:{"LCV":"Scrappage creating replacement demand. New LCVs have 3-5x higher electronics content vs 15-yr-old vehicles.","HCV":"11L+ trucks eligible for scrapping. New trucks have 3-5x more electronics. ₹15K Cr replacement opportunity."}},
{id:"cvfleet",cat:"T",name:"Fleet Digitization & Telematics",desc:"AIS-140 GPS + RFID. Fleet platforms (BlackBuck, Rivigo) scaling. Predictive maintenance -30% downtime.",src:"MoRTH · Industry",st:"Active",isNew:false,origin:"2018 — AIS-140 mandate; fleet tech scaling 2022+ with BlackBuck, Rivigo",rel:{"4W_PV":"L","LCV":"H","HCV":"H","2W":"L","3W":"M","Tractor":"M"},pos:{jan25:[7,7],jan26:[8,7.5],mar26:[8.5,7.5]},pil:["Infotainment","Services","Cloud","Solutions"],segNote:{"LCV":"Last-mile fleet digitization booming with e-commerce. Amazon, Flipkart mandating telematics. ₹200 Cr market.","HCV":"Full telematics — fuel monitoring, driver scoring, predictive maintenance. 60%+ adoption in organized fleets.","Tractor":"Rental/shared tractor IoT for utilization tracking. Early but growing with JFarm, EM3."}},
{id:"3wev",cat:"E",name:"3W EV Dominance (>50%)",desc:"Electric 3W >50% in Delhi, Bangalore. Mahindra Treo, Piaggio leading. BaaS reducing upfront cost 40%.",src:"Vahan · IBEF CY2025",st:"Dominant",isNew:false,origin:"2019 — first mass e-3W; crossed 50% in Delhi 2024",rel:{"4W_PV":"L","LCV":"L","HCV":"L","2W":"L","3W":"H","Tractor":"L"},pos:{jan25:[7.5,8],jan26:[8.5,8.5],mar26:[9,9]},pil:["Energy","Motion","Solutions"],segNote:{"3W":"Fastest EV transition globally. BaaS enabling ₹1.5L cheaper upfront. Cities targeting 100% e-3W by 2028-30. Battery swap in 90 seconds."}},
{id:"euFta",cat:"E",name:"India-EU FTA (Jan 2026)",desc:"Concluded 27 Jan 2026. Europe 29.5% of $22.9B exports. Tariff 6.5%→0% over 7 years.",src:"MoCI Jan 2026 · ACMA FY25",st:"Concluded",isNew:true,origin:"Jun 2022 — negotiations launched; 27 Jan 2026 concluded",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"M","3W":"M","Tractor":"M"},pos:{jan25:[5,6.5],jan26:[8,8.5],mar26:[9,9]},pil:["Motion","Body & Comfort","Energy","Semiconductors"],segNote:{"4W_PV":"0% tariff access to $300B+ EU aftermarket. ACMA projects $4-6B additional exports by 2030. Brake, steering, body components primary beneficiaries.","HCV":"CV component exports to EU fleet operators accelerating. Type-approval harmonization reduces compliance cost 40%.","LCV":"LCV aftermarket components — filters, brake pads, clutch plates gaining EU access.","Tractor":"Tractor component exports to EU — smaller but growing. Escorts, TAFE already export to EU markets."}},
{id:"euCbam",cat:"En",name:"EU CBAM Carbon Border Tax",desc:"Steel/aluminum-intensive parts face 20-35% carbon cost premium for EU exports from 2026.",src:"EU CBAM Regulation · ACMA",st:"Implementing",isNew:true,origin:"Oct 2023 — EU CBAM transitional phase; Jan 2026 permanent phase begins",rel:{"4W_PV":"H","LCV":"H","HCV":"H","2W":"M","3W":"L","Tractor":"M"},pos:{jan25:null,jan26:[5.5,7],mar26:[7,8]},pil:["Body & Comfort","Motion","Energy"],segNote:{"4W_PV":"Body panels, chassis, wheels face carbon premium. Green steel sourcing = competitive advantage. ₹2-5K cost per vehicle.","HCV":"Heavy steel content in CV components. CBAM cost ₹8,000-15,000 per vehicle worth of components. Green steel sourcing critical.","Tractor":"Tractor components exported to EU face moderate CBAM — castings, forgings primarily affected."}},
];

const PILLARS=[
{id:"Solutions",label:"Solutions",color:PILLAR_COLORS.Solutions,layer:0,desc:"Fleet health, charging, logistics platforms"},
{id:"Services",label:"Services",color:PILLAR_COLORS.Services,layer:0,desc:"Maps, battery cloud, V2X warnings"},
{id:"Cloud",label:"Cloud",color:PILLAR_COLORS.Cloud,layer:0,desc:"OTA, V2X infra, vehicle analytics"},
{id:"ADAS",label:"ADAS",color:PILLAR_COLORS.ADAS,layer:1,desc:"AEB, ACC, LKA, DMS, BSD, parking"},
{id:"Motion",label:"Motion",color:PILLAR_COLORS.Motion,layer:1,desc:"Powertrain, drivetrain, braking, steering"},
{id:"Energy",label:"Energy",color:PILLAR_COLORS.Energy,layer:1,desc:"Battery, power electronics, thermal"},
{id:"Body & Comfort",label:"Body & Comfort",color:PILLAR_COLORS["Body & Comfort"],layer:1,desc:"Panels, chassis, interior, lighting"},
{id:"Infotainment",label:"Infotainment",color:PILLAR_COLORS.Infotainment,layer:1,desc:"Displays, sensors, wiring, electronics"},
{id:"OS",label:"Vehicle OS",color:PILLAR_COLORS.OS,layer:2,desc:"AUTOSAR, Linux, vehicle OS"},
{id:"Compute",label:"Compute",color:PILLAR_COLORS.Compute,layer:2,desc:"Central, zone, domain controllers"},
{id:"ECUs",label:"ECUs",color:PILLAR_COLORS.ECUs,layer:2,desc:"ADAS, integration, generic ECUs"},
{id:"Semiconductors",label:"Semiconductors",color:PILLAR_COLORS.Semiconductors,layer:3,desc:"Power, SiC, MEMS, radar"},
{id:"Actuators",label:"Actuators",color:PILLAR_COLORS.Actuators,layer:3,desc:"Sensors, e-motors, brakes, injectors"},
];
const PM=Object.fromEntries(PILLARS.map(p=>[p.id,p]));

const FALLBACK_TECHS=[
{n:"Auto Emergency Braking",p:"ADAS",mat:"Growth",inc:"Radar, camera, ECU, actuator integration",sz:{"4W_PV":1500,"LCV":200,"HCV":350,"2W":50,"3W":12,"Tractor":8},cagr:20.1,conf:"M",src:"Mordor Intelligence Jan 2026"},
{n:"Adaptive Cruise Control",p:"ADAS",mat:"Growth",inc:"Long-range radar, sensor fusion, throttle/brake",sz:{"4W_PV":1200,"LCV":90,"HCV":220,"2W":25,"3W":5,"Tractor":15},cagr:19.2,conf:"M",src:"Mordor Intelligence"},
{n:"Lane Keep Assist",p:"ADAS",mat:"Emerging",inc:"Front camera, EPS integration, lane detection AI",sz:{"4W_PV":950,"LCV":55,"HCV":130,"2W":10,"3W":3,"Tractor":5},cagr:22.5,conf:"M",src:"Mordor Intelligence Jan 2026"},
{n:"Driver Monitoring System",p:"ADAS",mat:"Emerging",inc:"IR camera, facial recognition, fatigue detection",sz:{"4W_PV":550,"LCV":45,"HCV":180,"2W":18,"3W":5,"Tractor":3},cagr:28.4,conf:"M",src:"Mordor — MoRTH mandate"},
{n:"Blind Spot Detection",p:"ADAS",mat:"Growth",inc:"Side radar, warning indicators, cross-traffic alert",sz:{"4W_PV":750,"LCV":65,"HCV":110,"2W":12,"3W":4,"Tractor":2},cagr:16.8,conf:"M",src:"Mordor Intelligence"},
{n:"Traffic Sign Recognition",p:"ADAS",mat:"Emerging",inc:"Camera, image classification, speed limit overlay",sz:{"4W_PV":420,"LCV":22,"HCV":55,"2W":6,"3W":2,"Tractor":1},cagr:25.0,conf:"L",src:"Expert Market Research [Est.]"},
{n:"Parking Assist / APA",p:"ADAS",mat:"Growth",inc:"Ultrasonic sensors, surround camera, steering",sz:{"4W_PV":800,"LCV":30,"HCV":20,"2W":5,"3W":2,"Tractor":1},cagr:18.0,conf:"L",src:"Mordor — parking"},
{n:"Surround View Monitor",p:"ADAS",mat:"Emerging",inc:"4 fisheye cameras, image stitching, 3D projection",sz:{"4W_PV":600,"LCV":20,"HCV":40,"2W":3,"3W":2,"Tractor":1},cagr:24.0,conf:"L",src:"[Est.] 360° camera"},
{n:"Powertrain – Engine",p:"Motion",mat:"Mature",inc:"Engine block, pistons, turbo, fuel injection, gaskets",sz:{"4W_PV":32000,"LCV":6000,"HCV":9500,"2W":13000,"3W":2200,"Tractor":12000},cagr:5.5,conf:"H",src:"ACMA FY25"},
{n:"Transmission & Drivetrain",p:"Motion",mat:"Mature",inc:"Gearbox, clutch, driveshaft, differential, CV joints",sz:{"4W_PV":25000,"LCV":3200,"HCV":5800,"2W":6500,"3W":900,"Tractor":8000},cagr:6.5,conf:"H",src:"ACMA FY25"},
{n:"xEV Powertrain",p:"Motion",mat:"Emerging",inc:"Electric motor, inverter, reduction gear, controller",sz:{"4W_PV":3000,"LCV":450,"HCV":350,"2W":4000,"3W":1700,"Tractor":200},cagr:28.0,conf:"M",src:"ACMA — EV 6.7% of OEM"},
{n:"e-Axle Integrated Drive",p:"Motion",mat:"Emerging",inc:"Motor + inverter + gearbox in one unit, cooling",sz:{"4W_PV":1100,"LCV":120,"HCV":90,"2W":550,"3W":220,"Tractor":50},cagr:32.0,conf:"L",src:"Bosch Research [Est.]"},
{n:"Braking Systems",p:"Motion",mat:"Mature",inc:"Disc/drum brakes, ABS module, pads, calipers, lines",sz:{"4W_PV":18000,"LCV":2600,"HCV":4200,"2W":5200,"3W":650,"Tractor":3500},cagr:5.5,conf:"H",src:"ACMA FY25"},
{n:"Suspension System",p:"Motion",mat:"Mature",inc:"Shock absorbers, springs, control arms, stabilizers",sz:{"4W_PV":16500,"LCV":2100,"HCV":3700,"2W":4200,"3W":420,"Tractor":4000},cagr:7.5,conf:"H",src:"ACMA FY25"},
{n:"Steering (EPS)",p:"Motion",mat:"Mature",inc:"EPS motor, rack & pinion, steering column, torque sensor",sz:{"4W_PV":6500,"LCV":850,"HCV":1300,"2W":220,"3W":110,"Tractor":2000},cagr:8.0,conf:"H",src:"ACMA FY25"},
{n:"xEV Battery Pack",p:"Energy",mat:"Growth",inc:"Li-ion cells, module assembly, cooling plates, BMS",sz:{"4W_PV":3500,"LCV":350,"HCV":450,"2W":4500,"3W":1400,"Tractor":100},cagr:25.0,conf:"M",src:"IBEF — $2.22B"},
{n:"xEV Power Electronics",p:"Energy",mat:"Growth",inc:"Inverter, DC-DC converter, onboard charger, PDU",sz:{"4W_PV":2200,"LCV":220,"HCV":280,"2W":1700,"3W":450,"Tractor":60},cagr:22.0,conf:"M",src:"IndexBox + PLI"},
{n:"Fuel Supply (DI/GDI)",p:"Energy",mat:"Mature",inc:"Fuel pump, injectors, fuel rail, pressure regulator",sz:{"4W_PV":5200,"LCV":850,"HCV":1600,"2W":3200,"3W":320,"Tractor":2500},cagr:4.5,conf:"H",src:"PwC-Bosch"},
{n:"Exhaust & Emission",p:"Energy",mat:"Mature",inc:"DPF, SCR, catalytic converter, EGR valve, DEF tank",sz:{"4W_PV":10500,"LCV":1600,"HCV":3200,"2W":2700,"3W":420,"Tractor":3000},cagr:4.0,conf:"H",src:"BS-VI mandate"},
{n:"Thermal Mgmt / HVAC",p:"Energy",mat:"Growth",inc:"Compressor, condenser, heat pump, battery chiller",sz:{"4W_PV":4500,"LCV":600,"HCV":900,"2W":200,"3W":80,"Tractor":300},cagr:12.0,conf:"M",src:"EV thermal"},
{n:"Battery Mgmt System",p:"Energy",mat:"Emerging",inc:"Cell monitoring IC, balancing circuit, SOC algorithm",sz:{"4W_PV":800,"LCV":80,"HCV":100,"2W":600,"3W":200,"Tractor":30},cagr:30.0,conf:"L",src:"[Est.]"},
{n:"Body Panels & Structures",p:"Body & Comfort",mat:"Mature",inc:"Doors, hood, fenders, bumpers, BIW stampings",sz:{"4W_PV":34000,"LCV":3200,"HCV":5200,"2W":6500,"3W":1100,"Tractor":3000},cagr:4.0,conf:"H",src:"ACMA FY25"},
{n:"Chassis Frame",p:"Body & Comfort",mat:"Declining",inc:"Ladder frame, monocoque shell, cross-members, subframe",sz:{"4W_PV":33000,"LCV":3700,"HCV":6300,"2W":4200,"3W":850,"Tractor":5500},cagr:2.0,conf:"H",src:"ACMA FY25"},
{n:"Interior Trim",p:"Body & Comfort",mat:"Growth",inc:"Dashboard, door panels, headliner, console, surfaces",sz:{"4W_PV":26000,"LCV":1100,"HCV":1600,"2W":2200,"3W":320,"Tractor":800},cagr:11.0,conf:"H",src:"SUV premiumization"},
{n:"Seats & Restraints",p:"Body & Comfort",mat:"Growth",inc:"Seat frames, foam, airbags (6+), seatbelts, pretensioners",sz:{"4W_PV":23000,"LCV":1300,"HCV":2100,"2W":1600,"3W":320,"Tractor":1200},cagr:12.0,conf:"H",src:"BNCAP 6-airbag"},
{n:"Adaptive Lighting",p:"Body & Comfort",mat:"Growth",inc:"LED headlamps, DRLs, matrix beam, tail lamps, ambient",sz:{"4W_PV":5500,"LCV":420,"HCV":650,"2W":2200,"3W":220,"Tractor":400},cagr:14.0,conf:"M",src:"LED standard"},
{n:"Glass & Glazing",p:"Body & Comfort",mat:"Mature",inc:"Windshield, tempered glass, sunroof, HUD reflective",sz:{"4W_PV":8500,"LCV":800,"HCV":1200,"2W":500,"3W":200,"Tractor":600},cagr:6.0,conf:"M",src:"PwC-Bosch"},
{n:"Wheels & Components",p:"Body & Comfort",mat:"Mature",inc:"Alloy wheels, steel rims, hub bearings, TPMS sensors",sz:{"4W_PV":22000,"LCV":2000,"HCV":3500,"2W":5000,"3W":600,"Tractor":4000},cagr:5.0,conf:"H",src:"ACMA"},
{n:"Infotainment & Telematics",p:"Infotainment",mat:"Growth",inc:"Touchscreen, SoC, speakers, amplifier, CarPlay",sz:{"4W_PV":21000,"LCV":1600,"HCV":2700,"2W":2800,"3W":450,"Tractor":300},cagr:16.0,conf:"H",src:"PS Market Research"},
{n:"Safety Electronics",p:"Infotainment",mat:"Growth",inc:"Airbag ECU, crash sensors, rollover detect, e-call",sz:{"4W_PV":14000,"LCV":1100,"HCV":1900,"2W":900,"3W":220,"Tractor":200},cagr:18.0,conf:"H",src:"IMARC — $3.86B"},
{n:"Sensors (O2/NOx/PM)",p:"Infotainment",mat:"Growth",inc:"Lambda sensor, NOx sensor, PM sensor, temp/pressure",sz:{"4W_PV":10500,"LCV":850,"HCV":1300,"2W":1600,"3W":220,"Tractor":500},cagr:12.2,conf:"H",src:"PS Market Research"},
{n:"ECM / BCM Electronics",p:"Infotainment",mat:"Growth",inc:"Engine control module, body control, power windows",sz:{"4W_PV":14500,"LCV":1000,"HCV":1500,"2W":1200,"3W":200,"Tractor":400},cagr:10.0,conf:"M",src:"Auto electronics"},
{n:"Wiring & Harness",p:"Infotainment",mat:"Mature",inc:"Main harness, engine harness, CAN bus, connectors, fuses",sz:{"4W_PV":18500,"LCV":1400,"HCV":2200,"2W":2000,"3W":350,"Tractor":800},cagr:7.0,conf:"H",src:"ACMA"},
{n:"Fleet Health / RideCare",p:"Solutions",mat:"Emerging",inc:"Vibration analytics, predictive maintenance, OBD",sz:{"4W_PV":400,"LCV":200,"HCV":350,"2W":50,"3W":30,"Tractor":20},cagr:25.0,conf:"L",src:"[Est.] Bosch Connected"},
{n:"Charging / eMobility",p:"Solutions",mat:"Emerging",inc:"AC/DC chargers, charge mgmt, payment, load balancing",sz:{"4W_PV":600,"LCV":50,"HCV":100,"2W":300,"3W":100,"Tractor":10},cagr:40.0,conf:"L",src:"29K+ stations Aug 2025"},
{n:"Logistics Fleet OS",p:"Solutions",mat:"Emerging",inc:"Route optimization, fuel mgmt, driver scoring, compliance",sz:{"4W_PV":200,"LCV":300,"HCV":500,"2W":80,"3W":150,"Tractor":50},cagr:22.0,conf:"L",src:"[Est.] AIS-140"},
{n:"Connected Map Services",p:"Services",mat:"Growth",inc:"HD maps, real-time traffic, EV range map, POI data",sz:{"4W_PV":600,"LCV":100,"HCV":200,"2W":150,"3W":30,"Tractor":20},cagr:18.0,conf:"L",src:"[Est.]"},
{n:"Battery in the Cloud",p:"Services",mat:"Emerging",inc:"SOH prediction, degradation model, warranty analytics",sz:{"4W_PV":200,"LCV":20,"HCV":30,"2W":150,"3W":50,"Tractor":5},cagr:35.0,conf:"L",src:"[Est.]"},
{n:"V2X Safety Warnings",p:"Services",mat:"Emerging",inc:"Collision warnings, hazard alerts, signal phase, C-V2X",sz:{"4W_PV":100,"LCV":20,"HCV":50,"2W":10,"3W":5,"Tractor":2},cagr:30.0,conf:"L",src:"[Est.]"},
{n:"OTA Update Platform",p:"Cloud",mat:"Emerging",inc:"FOTA/SOTA, delta update, rollback, campaign mgmt",sz:{"4W_PV":900,"LCV":35,"HCV":70,"2W":250,"3W":35,"Tractor":10},cagr:35.0,conf:"L",src:"Tata/M&M/Ather [Est.]"},
{n:"V2X Cloud Infra",p:"Cloud",mat:"Emerging",inc:"Edge computing, MQTT broker, digital twin, APIs",sz:{"4W_PV":300,"LCV":30,"HCV":60,"2W":20,"3W":10,"Tractor":5},cagr:28.0,conf:"L",src:"[Est.]"},
{n:"Vehicle Analytics",p:"Cloud",mat:"Emerging",inc:"Fleet dashboards, usage patterns, anomaly detection, ML",sz:{"4W_PV":400,"LCV":50,"HCV":80,"2W":60,"3W":20,"Tractor":15},cagr:30.0,conf:"L",src:"[Est.]"},
{n:"AUTOSAR Classic",p:"OS",mat:"Mature",inc:"RTE, BSW modules, COM stack, diagnostics (UDS/OBD)",sz:{"4W_PV":1500,"LCV":200,"HCV":300,"2W":100,"3W":30,"Tractor":50},cagr:6.0,conf:"L",src:"[Est.]"},
{n:"AUTOSAR Adaptive",p:"OS",mat:"Emerging",inc:"POSIX OS, service-oriented arch, REST APIs, containers",sz:{"4W_PV":600,"LCV":40,"HCV":80,"2W":30,"3W":10,"Tractor":5},cagr:25.0,conf:"L",src:"[Est.] SDV enabler"},
{n:"Linux Vehicle OS",p:"OS",mat:"Emerging",inc:"AGL, Ubuntu Core, hypervisor, container runtime",sz:{"4W_PV":400,"LCV":20,"HCV":40,"2W":50,"3W":5,"Tractor":3},cagr:30.0,conf:"L",src:"[Est.]"},
{n:"Central Compute Unit",p:"Compute",mat:"Emerging",inc:"High-perf SoC, vehicle server, Ethernet backbone",sz:{"4W_PV":1300,"LCV":55,"HCV":90,"2W":110,"3W":22,"Tractor":10},cagr:28.0,conf:"L",src:"[Est.]"},
{n:"Zone Controllers",p:"Compute",mat:"Emerging",inc:"Zone ECU, local I/O, Ethernet switch, power distribution",sz:{"4W_PV":800,"LCV":30,"HCV":60,"2W":40,"3W":10,"Tractor":5},cagr:30.0,conf:"L",src:"[Est.]"},
{n:"Domain Controllers",p:"Compute",mat:"Growth",inc:"ADAS domain, cockpit domain, body domain controller",sz:{"4W_PV":1800,"LCV":100,"HCV":200,"2W":80,"3W":20,"Tractor":15},cagr:20.0,conf:"L",src:"[Est.] ADAS/Cockpit"},
{n:"ADAS Integration ECU",p:"ECUs",mat:"Growth",inc:"Sensor fusion ECU, ADAS platform, radar/camera IF",sz:{"4W_PV":2000,"LCV":150,"HCV":300,"2W":50,"3W":15,"Tractor":10},cagr:22.0,conf:"M",src:"Bosch platform"},
{n:"Vehicle Integration ECU",p:"ECUs",mat:"Mature",inc:"Gateway ECU, CAN-to-Ethernet, OBD port, power mgmt",sz:{"4W_PV":3500,"LCV":300,"HCV":500,"2W":200,"3W":50,"Tractor":100},cagr:8.0,conf:"M",src:"ACMA electronics"},
{n:"Generic ECU Modules",p:"ECUs",mat:"Mature",inc:"Window lift, mirror, seat, wiper, HVAC control modules",sz:{"4W_PV":5000,"LCV":400,"HCV":700,"2W":300,"3W":80,"Tractor":150},cagr:5.0,conf:"M",src:"Declining — centralization"},
{n:"Power Semiconductor",p:"Semiconductors",mat:"Growth",inc:"IGBTs, MOSFETs, power diodes, gate drivers",sz:{"4W_PV":2500,"LCV":200,"HCV":350,"2W":400,"3W":100,"Tractor":80},cagr:15.0,conf:"M",src:"IndexBox India"},
{n:"SiC Semiconductors",p:"Semiconductors",mat:"Emerging",inc:"SiC MOSFET, SiC diode, SiC module (800V inverter)",sz:{"4W_PV":900,"LCV":45,"HCV":65,"2W":220,"3W":55,"Tractor":10},cagr:38.0,conf:"M",src:"RIR Odisha fab"},
{n:"MEMS Sensors",p:"Semiconductors",mat:"Growth",inc:"Accelerometer, gyroscope, pressure sensor, microphone",sz:{"4W_PV":1800,"LCV":150,"HCV":250,"2W":200,"3W":40,"Tractor":60},cagr:14.0,conf:"M",src:"Pressure/accel/gyro"},
{n:"Radar Modules (77GHz)",p:"Semiconductors",mat:"Emerging",inc:"MMIC chip, antenna PCB, radome, signal processor",sz:{"4W_PV":1200,"LCV":80,"HCV":200,"2W":30,"3W":8,"Tractor":5},cagr:28.0,conf:"M",src:"IndexBox Feb 2026"},
{n:"ADAS Sensors",p:"Actuators",mat:"Growth",inc:"Camera modules, LiDAR, ultrasonic, sensor cleaning",sz:{"4W_PV":3500,"LCV":220,"HCV":430,"2W":110,"3W":22,"Tractor":8},cagr:22.0,conf:"M",src:"Mordor + PS Market"},
{n:"E-motors & Compressors",p:"Actuators",mat:"Emerging",inc:"BLDC motors, e-compressor, EPS motor, cooling fan",sz:{"4W_PV":2000,"LCV":200,"HCV":300,"2W":2500,"3W":800,"Tractor":100},cagr:25.0,conf:"M",src:"EV demand"},
{n:"DPB / EPS Actuators",p:"Actuators",mat:"Growth",inc:"Decoupled power brake, electric booster, steer-by-wire",sz:{"4W_PV":4000,"LCV":400,"HCV":700,"2W":300,"3W":80,"Tractor":500},cagr:10.0,conf:"M",src:"By-wire for ADAS"},
{n:"ICE Fuel Injectors",p:"Actuators",mat:"Mature",inc:"GDI injector, common rail, piezo injector, nozzle",sz:{"4W_PV":6000,"LCV":900,"HCV":1500,"2W":2000,"3W":300,"Tractor":2500},cagr:3.0,conf:"H",src:"Declining with EV"},
{n:"Cockpit Integration",p:"Actuators",mat:"Growth",inc:"Digital cluster, HUD, multi-display, OLED panels",sz:{"4W_PV":2500,"LCV":200,"HCV":350,"2W":300,"3W":50,"Tractor":30},cagr:18.0,conf:"L",src:"Digital cockpit fusion"},
// ── Bosch-stack additions: Solutions / Services / OS / Compute / Semis / Actuators ──
{n:"RideCare / Fleet Health Platform",p:"Solutions",mat:"Emerging",inc:"Vibration analytics, predictive maintenance, OBD diagnostics, fleet uptime dashboards",sz:{"4W_PV":400,"LCV":200,"HCV":350,"2W":50,"3W":30,"Tractor":0},cagr:25.0,conf:"L",src:"AI Estimate: Bosch Connected"},
{n:"Charging Service (eMobility)",p:"Solutions",mat:"Emerging",inc:"AC/DC chargers, charge management software, payment integration, load balancing",sz:{"4W_PV":600,"LCV":50,"HCV":100,"2W":300,"3W":100,"Tractor":0},cagr:40.0,conf:"M",src:"Derived: Vahan EV data"},
{n:"State of Health Report",p:"Solutions",mat:"Emerging",inc:"SOH prediction, residual value, warranty risk, second-life routing",sz:{"4W_PV":180,"LCV":25,"HCV":40,"2W":100,"3W":50,"Tractor":0},cagr:35.0,conf:"L",src:"AI Estimate: Bosch Battery-in-Cloud"},
{n:"Logistics Fleet OS",p:"Solutions",mat:"Emerging",inc:"Route optimization, fuel monitoring, driver scoring, AIS-140 compliance",sz:{"4W_PV":200,"LCV":300,"HCV":500,"2W":0,"3W":150,"Tractor":0},cagr:22.0,conf:"L",src:"Derived: AIS-140 mandate"},
{n:"Wrong-Way Driver Warning",p:"Services",mat:"Emerging",inc:"Cloud detection, driver alert via head unit, V2X broadcast",sz:{"4W_PV":50,"LCV":10,"HCV":30,"2W":0,"3W":0,"Tractor":0},cagr:28.0,conf:"L",src:"AI Estimate: Bosch services"},
{n:"Connected Map Services",p:"Services",mat:"Growth",inc:"HD maps, real-time traffic, EV range maps, POI data, lane-level routing",sz:{"4W_PV":600,"LCV":100,"HCV":200,"2W":150,"3W":0,"Tractor":0},cagr:18.0,conf:"M",src:"Derived: MapmyIndia + HERE India"},
{n:"Battery in the Cloud",p:"Services",mat:"Emerging",inc:"BMS analytics, degradation modeling, warranty optimization, cell-level diagnostics",sz:{"4W_PV":200,"LCV":20,"HCV":30,"2W":150,"3W":50,"Tractor":0},cagr:35.0,conf:"L",src:"AI Estimate: Bosch Battery-in-Cloud"},
{n:"Driving Functions L0-L3",p:"OS",mat:"Growth",inc:"Path planning, behavior prediction, sensor fusion, driving policy, OEDR",sz:{"4W_PV":1100,"LCV":90,"HCV":200,"2W":0,"3W":0,"Tractor":0},cagr:22.0,conf:"M",src:"Derived: Mordor ADAS"},
{n:"Parking Software",p:"OS",mat:"Growth",inc:"APA algorithms, valet parking software, parking spot detection",sz:{"4W_PV":350,"LCV":40,"HCV":30,"2W":0,"3W":0,"Tractor":0},cagr:18.0,conf:"L",src:"AI Estimate: Mordor parking-assist"},
{n:"Vehicle Motion Management",p:"OS",mat:"Emerging",inc:"Coordinated steer-brake-drive control, dynamic torque vectoring, integrated chassis control",sz:{"4W_PV":480,"LCV":60,"HCV":110,"2W":0,"3W":0,"Tractor":0},cagr:26.0,conf:"L",src:"AI Estimate: Bosch VMM"},
{n:"ADAS Integration Platform",p:"Compute",mat:"Growth",inc:"ADAS domain controller, sensor fusion ECU, NVIDIA DRIVE / Qualcomm Snapdragon Ride / Bosch DASy",sz:{"4W_PV":1400,"LCV":110,"HCV":220,"2W":0,"3W":0,"Tractor":0},cagr:24.0,conf:"M",src:"Derived: Mordor ADAS DCU"},
{n:"Vehicle Integration Platform",p:"Compute",mat:"Emerging",inc:"Central vehicle computer, zonal compute, cross-domain orchestration, service-oriented arch",sz:{"4W_PV":900,"LCV":80,"HCV":140,"2W":0,"3W":0,"Tractor":0},cagr:28.0,conf:"L",src:"AI Estimate: SDV transition"},
{n:"Automotive ASIC",p:"Semiconductors",mat:"Growth",inc:"Custom ICs for radar, camera serializers, ADAS-specific accelerators, BMS ICs",sz:{"4W_PV":700,"LCV":60,"HCV":100,"2W":100,"3W":25,"Tractor":20},cagr:16.0,conf:"L",src:"AI Estimate: IndexBox auto-IC"},
{n:"Comfort Actuators",p:"Actuators",mat:"Mature",inc:"Power window motors, seat motors, sunroof actuators, mirror motors, HVAC blower",sz:{"4W_PV":1800,"LCV":200,"HCV":350,"2W":60,"3W":15,"Tractor":40},cagr:7.5,conf:"M",src:"Derived: ACMA body & comfort"},
];

/* ═══════════════════════════════════════════════════════════════
   MAIN COMPONENT
   ═══════════════════════════════════════════════════════════════ */
export default function MobilityIntelligence(){
  const[dk,setDk]=useState(false);
  const[seg,setSeg]=useState("4W_PV");
  const[view,setView]=useState(1);
  const[v1Sel,setV1Sel]=useState(null);
  const[v1Compare,setV1Compare]=useState([]);
  const[v1Cat,setV1Cat]=useState("all");
  const[v1Top,setV1Top]=useState(20);// 0=all,5,10,15,20
  const[v1Baseline,setV1Baseline]=useState("now");// "now" | "jan26" | "jan25"
  const[v2Pil,setV2Pil]=useState(null);
  const[v3P,setV3P]=useState("all");
  const[v3T,setV3T]=useState(null);
  const[v3Year,setV3Year]=useState(2030);
  const[v3Stage,setV3Stage]=useState("all");
  const[v3Top,setV3Top]=useState(0);
  const[curr,setCurr]=useState("INR");// INR or EUR

  // ── LIVE API DATA STATE ─────────────────────────────────
  // Starts with fallback (hardcoded) data, replaces with API data on load
  const[PESTEL,setPESTEL]=useState(FALLBACK_PESTEL);
  const[TECHS,setTECHS]=useState(FALLBACK_TECHS);
  const[apiStatus,setApiStatus]=useState("loading"); // "loading"|"live"|"fallback"
  const[aiAnalysis,setAiAnalysis]=useState(null); // AI-generated detail panel
  const[aiLoading,setAiLoading]=useState(false);
  const[lastRefresh,setLastRefresh]=useState(null);
  const[healthData,setHealthData]=useState(null);

  // ── VIEW 4: COMPETITOR LANDSCAPE STATE ────────────────
  const[v4Pillar,setV4Pillar]=useState("ADAS");
  const[v4Data,setV4Data]=useState(null);
  const[v4TechData,setV4TechData]=useState(null);
  const[v4Mode,setV4Mode]=useState("overview"); // "overview" | "drilldown"
  const[v4DrillTech,setV4DrillTech]=useState(null);
  const[v4Loading,setV4Loading]=useState(false);

  // ── TIMELINE COMPARE: real history from API ────────────
  const[compareTimelines,setCompareTimelines]=useState({});

  // ── HEALTH POLLING ──────────────────────────────────────
  const[validationStats,setValidationStats]=useState(null);
  const[liveEurRate,setLiveEurRate]=useState(EUR_RATE);
  const[eurRateMeta,setEurRateMeta]=useState(null);
  const[auditStats,setAuditStats]=useState(null);
  useEffect(()=>{
    const poll=async()=>{
      try{
        const res=await fetch(`${API_BASE}/api/health`);
        if(res.ok) setHealthData(await res.json());
        const vs=await fetch(`${API_BASE}/api/refresh/validation-stats?days=7`);
        if(vs.ok) setValidationStats(await vs.json());
        const er=await fetch(`${API_BASE}/api/refresh/exchange-rate`);
        if(er.ok){
          const erData=await er.json();
          if(erData.rate_eur_to_inr) setLiveEurRate(erData.rate_eur_to_inr);
          setEurRateMeta(erData);
        }
        const ar=await fetch(`${API_BASE}/api/refresh/audit-stats?days=7`);
        if(ar.ok) setAuditStats(await ar.json());
      }catch(e){}
    };
    poll();
    const interval=setInterval(poll,120000);
    return()=>clearInterval(interval);
  },[]);

  // ── FETCH DATA FROM LIVE BACKEND ────────────────────────
  // Runs once on mount. If API is reachable, replaces hardcoded data.
  // If API fails, keeps using the hardcoded fallback (dashboard always works).
  useEffect(()=>{
    let cancelled=false;
    async function loadFromAPI(){
      try{
        const[pestelRes,techRes]=await Promise.all([
          fetch(`${API_BASE}/api/pestel/?segment=${seg}`),
          fetch(`${API_BASE}/api/techs/?segment=${seg}`)
        ]);
        if(!pestelRes.ok||!techRes.ok) throw new Error("API returned non-200");
        const pestelData=await pestelRes.json();
        const techData=await techRes.json();
        if(cancelled)return;
        if(pestelData.factors?.length>0){
          setPESTEL(transformPestel(pestelData.factors));
        }
        if(techData.technologies?.length>0){
          setTECHS(transformTechs(techData.technologies));
        }
        setApiStatus("live");
        setLastRefresh(new Date().toLocaleTimeString());
        console.log(`✅ Live API: ${pestelData.count} PESTEL, ${techData.count} techs`);
      }catch(e){
        if(!cancelled){
          setApiStatus("fallback");
          console.warn("⚠️ API unavailable, using fallback data:",e.message);
        }
      }
    }
    loadFromAPI();
    return()=>{cancelled=true;};
  },[seg]); // Re-fetch when segment changes

  // ── FETCH AI ANALYSIS ON BUBBLE CLICK ───────────────────
  // When user clicks a PESTEL bubble or tech bubble, fetch AI detail
  // ── FETCH VIEW 4 COMPETITOR DATA ───────────────────────
  useEffect(()=>{
    if(view!==4)return;
    setV4Loading(true);
    // When pillar or segment changes, also reset drilldown state.
    // This prevents the "stale tech in new segment" race that produces a blank panel.
    setV4DrillTech(null);
    setV4TechData(null);
    setV4Mode("overview");
    fetch(`${API_BASE}/api/competitors/pillar?pillar=${encodeURIComponent(v4Pillar)}&segment=${seg}`)
      .then(r=>r.json()).then(d=>{setV4Data(d);setV4Loading(false);})
      .catch(()=>setV4Loading(false));
  },[view,v4Pillar,seg]);

  useEffect(()=>{
    if(view!==4||!v4DrillTech)return;
    // Clear stale data immediately so user sees loading state instead of old tech's data
    setV4TechData(null);
    fetch(`${API_BASE}/api/competitors/tech?tech_code=${encodeURIComponent(v4DrillTech)}&segment=${seg}`)
      .then(r=>r.json()).then(d=>{
        // Defensive: if the API returns empty (tech doesn't exist in this segment), gracefully fall back
        if (!d || (!d.players?.length && !d.oem_sourcing?.length)) {
          setV4TechData(d); // still set so empty-state renders, not stuck loading
          return;
        }
        setV4TechData(d);
      })
      .catch(()=>{ setV4TechData(null); });
  },[v4DrillTech,seg]);

  // ── FETCH TIMELINE HISTORY FOR COMPARE ──────────────────
  useEffect(()=>{
    if(v1Compare.length===0)return;
    v1Compare.forEach(id=>{
      if(compareTimelines[id])return;
      fetch(`${API_BASE}/api/pestel/history/${id}`)
        .then(r=>r.json())
        .then(data=>{setCompareTimelines(prev=>({...prev,[id]:data.timeline||[]}));})
        .catch(()=>{});
    });
  },[v1Compare]);

  const fetchPestelAnalysis=useCallback(async(code)=>{
    setAiLoading(true); setAiAnalysis(null);
    try{
      const res=await fetch(`${API_BASE}/api/analysis/pestel/${code}?segment=${seg}`);
      if(res.ok){const data=await res.json(); setAiAnalysis(data);}
    }catch(e){console.warn("AI analysis fetch failed:",e);}
    finally{setAiLoading(false);}
  },[seg]);
  const fetchTechAnalysis=useCallback(async(code)=>{
    setAiLoading(true); setAiAnalysis(null);
    try{
      const res=await fetch(`${API_BASE}/api/analysis/tech/${code}?segment=${seg}`);
      if(res.ok){const data=await res.json(); setAiAnalysis(data);}
    }catch(e){console.warn("Tech analysis fetch failed:",e);}
    finally{setAiLoading(false);}
  },[seg]);
  _curr=curr;_liveEurRate=liveEurRate;// sync global formatter
  const svgRef=useRef(null);
  const[svgDim,setSvgDim]=useState({w:900,h:520});

  const t=dk?{bg:"#0a0e1a",card:"#111827",c:"#f1f5f9",c2:"#94a3b8",c3:"#64748b",acc:"#f97316",border:"#1e293b",btn:"#1e293b",bar:"#1e293b40",grid:"#1e293b80"}
           :{bg:"#f8fafc",card:"#ffffff",c:"#0f172a",c2:"#475569",c3:"#94a3b8",acc:"#f97316",border:"#e2e8f0",btn:"#f1f5f9",bar:"#e2e8f020",grid:"#e2e8f0"};
  const card=(x={})=>({background:t.card,borderRadius:"12px",border:`1px solid ${t.border}`,padding:"14px",...x});

  useEffect(()=>{
    if(!svgRef.current)return;
    const ro=new ResizeObserver(e=>{for(const en of e){setSvgDim({w:en.contentRect.width,h:Math.max(460,en.contentRect.height)});}});
    ro.observe(svgRef.current);return()=>ro.disconnect();
  },[view]);

  const isPestelRelevantForSegment=(factor,segment)=>{
    const rel=factor.rel?.[segment]||"L";
    if(rel==="L")return false;
    const name=(factor.name||"" ).toLowerCase();
    const desc=(factor.desc||factor.sr||factor.selection_reasoning||"").toLowerCase();
    const combined=name+" "+desc;
    // e-rickshaw — irrelevant for all segments we track
    if(combined.includes("rickshaw"))return false;
    // ── RULE 1: Explicit segment mention in NAME ──
    const has2W=name.match(/\b2w\b|two.?wheeler|e-2w|electric scooter/);
    const has3W=name.match(/\b3w\b|three.?wheeler|auto.?rickshaw|cargo 3w/);
    const hasTractor=name.match(/\btractor\b|farm equipment/);
    const hasHCV4W=name.match(/\bhcv\b|heavy commercial|\bbus\b|\btruck\b/);
    if(has3W&&!has2W){if(segment!=="3W")return false;}
    if(has2W&&!has3W){if(segment!=="2W")return false;}
    if(name.includes("for 4w")||name.includes("for all new 4w")||name.includes("for pv")){if(segment!=="4W_PV")return false;}
    if(name.match(/\bfor\s+(all\s+)?(new\s+)?hcv/)){if(segment!=="HCV"&&segment!=="LCV")return false;}
    if(hasTractor&&!name.match(/\b(lcv|hcv|4w)\b/)){if(segment!=="Tractor")return false;}
    // ── RULE 2: OEM-specific ──
    for(const[oem,segs]of Object.entries(OEM_SEGMENTS)){
      if(name.includes(oem)){if(!segs.includes(segment))return false;break;}
    }
    // ── RULE 3: Topic-specific ──
    for(const[topic,segs]of Object.entries(TOPIC_SEGMENTS)){
      if(name.includes(topic)){if(!segs.includes(segment))return false;break;}
    }
    // ── RULE 4: Keyword patterns in name ──
    if(name.match(/\b(suv|sedan|hatchback)\b/)&&!name.includes("lcv")){if(segment!=="4W_PV")return false;}
    if(name.match(/\b(scooter|motorcycle|two.?wheeler)\b/)){if(segment!=="2W")return false;}
    if(name.match(/\b(auto.?rickshaw|three.?wheeler)\b/)){if(segment!=="3W")return false;}
    if(name.match(/\b(precision.?ag|farm equipment)\b/)){if(segment!=="Tractor")return false;}
    // ── RULE 5: DESCRIPTION-BASED CHECK ──
    // Block factors whose descriptions clearly describe a different segment.
    if(segment==="2W"||segment==="3W"||segment==="Tractor"){
      if(desc.match(/directly supporting 4w|4w pv volume|4w pv sales|passenger vehicle market|suv dominance|hatchback market|sedan market/)){
        const segMention=segment==="2W"?/\b2w\b|two.?wheeler|motorcycle|scooter/
          :segment==="3W"?/\b3w\b|three.?wheeler|auto.?rickshaw/
          :/\btractor\b|farm|agri/;
        if(!desc.match(segMention))return false;
      }
    }
    // ── RULE 6: Mahindra — SUV/XUV/Thar/Scorpio factors are 4W-only ──
    if(combined.includes("mahindra")&&combined.match(/\b(suv|xuv|thar|scorpio)\b/)){
      if(segment!=="4W_PV")return false;
    }
    return true;
  };

  const segPestel=useMemo(()=>{
    let d=PESTEL.filter(f=>isPestelRelevantForSegment(f,seg));
    // Relevance penalty: downweight factors whose description targets a different segment
    d=d.map(f=>{
      const desc=(f.desc||f.sr||"").toLowerCase();
      let penalty=1.0;
      if(seg==="2W"||seg==="3W"||seg==="Tractor"){
        if(desc.match(/directly supporting 4w|4w pv volume|suv dominance|passenger vehicle market/)){
          const segPat=seg==="2W"?/\b2w\b|two.?wheeler|motorcycle|scooter/
                      :seg==="3W"?/\b3w\b|three.?wheeler|auto.?rickshaw/
                      :/tractor|farm|agri/;
          if(!desc.match(segPat))penalty=0.5;
        }
      }
      if((seg==="3W"||seg==="Tractor")&&f.cat==="E"){
        if(desc.match(/gdp growth|auto industry performance|component export/))penalty=Math.min(penalty,0.7);
      }
      return{...f,_penalty:penalty};
    });
    d.sort((a,b)=>{
      // Segment-aware ranking. Specificity boost rewards factors that are
      // diagnostically meaningful for THIS segment (not umbrella factors
      // that are H for all 6 segments). Also applies REL_MULT so M and L
      // factors don't tie with H ones at the top of the list.
      const REL_MULT = {H: 1.0, M: 0.7, L: 0.4};
      const _rankWeight = (f) => {
        const p = f.pos.mar26 || f.pos.jan26 || [0,0];
        let w = p[0] * p[1] * (CATEGORY_WEIGHTS[f.cat] || 1.0);
        const rel = f.rel?.[seg] || 'L';
        w *= (REL_MULT[rel] || 0.4);
        // Specificity: factors H for ≤3 of 6 segments are more diagnostic
        // than those H for all 6. Boost by 15%.
        const hCount = Object.values(f.rel || {}).filter(v => v === 'H').length;
        if (rel === 'H' && hCount > 0 && hCount <= 3) w *= 1.15;
        w *= (f._penalty || 1.0);
        return w;
      };
      return _rankWeight(b) - _rankWeight(a);
    });
    // Pre-nudge bubbles with identical L×I scores so the repulsion loop converges cleanly
    const posMap={};
    d.forEach(f=>{const p=f.pos.mar26||f.pos.jan26||[5,5];const key=`${Math.round(p[0]*2)/2}_${Math.round(p[1]*2)/2}`;if(!posMap[key])posMap[key]=[];posMap[key].push(f);});
    Object.values(posMap).forEach(group=>{
      if(group.length<=1)return;
      const spread = group.length <= 3 ? 0.7 : group.length <= 6 ? 0.6 : 0.5;
      group.forEach((f,i)=>{
        const angle=(2*Math.PI*i)/group.length - Math.PI/2;
        const base=f.pos.mar26||f.pos.jan26||[5,5];
        f._displayPos=[Math.max(1.5,Math.min(9.5,base[0]+Math.cos(angle)*spread)),Math.max(1.5,Math.min(9.5,base[1]+Math.sin(angle)*spread))];
      });
    });
    d.forEach(f=>{if(!f._displayPos){const p=f.pos.mar26||f.pos.jan26||[5,5];f._displayPos=[...p];}});
    // ── PASS 2: Force-repulsion for ANY overlapping pair ──
    for(let iter=0;iter<3;iter++){
      for(let i=0;i<d.length;i++){for(let j=i+1;j<d.length;j++){
        const a=d[i]._displayPos,b=d[j]._displayPos;
        const dx=a[0]-b[0],dy=a[1]-b[1],dist=Math.sqrt(dx*dx+dy*dy);
        const minDist=0.55;
        if(dist<minDist&&dist>0){
          const push=(minDist-dist)/2,angle=Math.atan2(dy,dx);
          a[0]=Math.max(1.5,Math.min(9.8,a[0]+Math.cos(angle)*push));
          a[1]=Math.max(1.5,Math.min(9.8,a[1]+Math.sin(angle)*push));
          b[0]=Math.max(1.5,Math.min(9.8,b[0]-Math.cos(angle)*push));
          b[1]=Math.max(1.5,Math.min(9.8,b[1]-Math.sin(angle)*push));
        }
      }}
    }
    return d;
  },[PESTEL,seg]);
  const filtPestel=useMemo(()=>{
    let d=v1Cat==="all"?segPestel:segPestel.filter(f=>f.cat===v1Cat);
    // ── Baseline filter: drop factors that didn't exist at the selected date
    if(v1Baseline==="jan25"){
      // Include factors with explicit jan25 data OR factors that existed by Jan 2025
      const _jan25 = new Date("2025-01-15");
      d=d.filter(f=>{
        if(f.pos?.jan25) return true;
        if(f.isFoundational) return true;
        if(f.originDate){const od=new Date(f.originDate); if(od<=_jan25) return true;}
        return false;
      });
    }else if(v1Baseline==="jan26"){
      const _jan26 = new Date("2026-01-15");
      d=d.filter(f=>{
        if(f.pos?.jan26) return true;
        if(f.isFoundational) return true;
        if(f.originDate){const od=new Date(f.originDate); if(od<=_jan26) return true;}
        return false;
      });
    }
    if(v1Top>0)d=d.slice(0,v1Top);
    return d;
  },[segPestel,v1Cat,v1Top,v1Baseline]);
  const isTechRelevantForSegment=(tech,segment,floor=50)=>{
    const nm=(tech.n||"").toLowerCase();const segSz=tech.sz?.[segment]||0;
    if(segSz<floor)return false;
    if(nm.includes("rickshaw"))return false;
    const excl=TECH_EXCLUSIONS[segment]||[];
    for(const e of excl){if(nm.includes(e))return false;}
    return true;
  };
  const segTechs=useMemo(()=>TECHS.filter(t=>isTechRelevantForSegment(t,seg)).map(t=>({...t,segSz:t.sz[seg]})).sort((a,b)=>b.segSz-a.segSz),[TECHS,seg]);

  /* ═══ VIEW 1: PESTEL RISK MAP ═══ */
  const renderV1=()=>{
    const W=svgDim.w,H=svgDim.h;
    const pad={l:50,r:20,t:30,b:42};
    const iW=W-pad.l-pad.r,iH=H-pad.t-pad.b;
    const isCompare=v1Compare.length>0;
    // ── AUTO-SCALE: zoom axes to actual data range ──
    const allPositions=filtPestel.map(f=>f._displayPos||f.pos.mar26||f.pos.jan26||[5,5]);
    const lkValues=allPositions.map(p=>p[0]);const impValues=allPositions.map(p=>p[1]);
    const lkMin=Math.max(1,Math.floor(Math.min(...(lkValues.length?lkValues:[5])))-1);
    const lkMax=Math.min(10,Math.ceil(Math.max(...(lkValues.length?lkValues:[5])))+1);
    const impMin=Math.max(1,Math.floor(Math.min(...(impValues.length?impValues:[5])))-1);
    const impMax=Math.min(10,Math.ceil(Math.max(...(impValues.length?impValues:[5])))+1);
    const lkRange=lkMax-lkMin||1;const impRange=impMax-impMin||1;
    const sx=(v)=>pad.l+((v-lkMin)/lkRange)*iW;
    const sy=(v)=>H-pad.b-((v-impMin)/impRange)*iH;
    const getR=f=>{const p=f.pos.mar26||f.pos.jan26;if(!p)return 10;return Math.max(9,Math.min(26,7+p[0]*p[1]/5));};

    // Baseline-aware position lookup
    const _posForBaseline=(f)=>{
      if(v1Baseline==="jan25"){
        // Prefer real anchor; fall back to current position shifted left/down slightly
        return f.pos?.jan25 || (f.pos?.mar26 ? [Math.max(1,f.pos.mar26[0]-1.5), Math.max(1,f.pos.mar26[1]-1)] : null);
      }
      if(v1Baseline==="jan26"){
        return f.pos?.jan26 || (f.pos?.mar26 ? [Math.max(1,f.pos.mar26[0]-0.5), f.pos.mar26[1]] : null);
      }
      return f._displayPos||f.pos?.mar26||f.pos?.jan26;
    };
    let bubbles=filtPestel.map(f=>{
      const p=_posForBaseline(f);
      if(!p) return null;
      return{...f,cx:sx(p[0]),cy:sy(p[1]),r:getR({...f,pos:{...f.pos,mar26:p}}),lk:p[0],imp:p[1],_baselinePos:p};
    }).filter(Boolean);
    // Strong repulsion: 40 passes, include label height in effective radius
    for(let pass=0;pass<40;pass++){for(let i=0;i<bubbles.length;i++){for(let j=i+1;j<bubbles.length;j++){
      const dx=bubbles[j].cx-bubbles[i].cx,dy=bubbles[j].cy-bubbles[i].cy,dist=Math.sqrt(dx*dx+dy*dy);
      const ri=bubbles[i].r+7,rj=bubbles[j].r+7,minD=ri+rj+14;
      if(dist<minD&&dist>0){const push=(minD-dist)/2*0.85,nx=dx/dist,ny=dy/dist;
        bubbles[i]={...bubbles[i],cx:bubbles[i].cx-nx*push,cy:bubbles[i].cy-ny*push};
        bubbles[j]={...bubbles[j],cx:bubbles[j].cx+nx*push,cy:bubbles[j].cy+ny*push};}
    }}}
    bubbles=bubbles.map(b=>({...b,cx:Math.max(pad.l+b.r,Math.min(W-pad.r-b.r,b.cx)),cy:Math.max(pad.t+b.r+14,Math.min(H-pad.b-b.r,b.cy))}));

    // ── Build conceptual anchor points (Jan 25 / Jan 26 / Now) ──
    // Trajectory uses three labeled checkpoints regardless of how many
    // raw snapshots exist in DB. Factors that didn't exist at an anchor
    // are marked with "emergedAt" so the chart shows an "Emerged" badge
    // instead of a misleading dot.
    // ── Origin-aware trajectory ──
    // Anchors in chronological order: Origin → Jan 2025 → Jan 2026 → Now
    const compareData=v1Compare.map(id=>{
      const f=PESTEL.find(p=>p.id===id);if(!f)return null;
      const _nowMonth = new Date().toLocaleDateString("en-US",{month:"short",year:"numeric"});
      const originDt = f.originDate ? new Date(f.originDate) : null;
      const jan25 = new Date("2025-01-15");
      const jan26 = new Date("2026-01-15");

      const pts = [];
      const nowPos = f.pos.mar26;
      if(!nowPos) return{f,pts};

      // Determine trend direction from LLM tag — used for synthesis when DB has no snapshots
      const sLow = String(f.st||f.trend||"").toLowerCase();
      const isEscalating = sLow.includes("escalat") || sLow.includes("acceler") || sLow.includes("rising") || sLow.includes("growing");
      const isDeescalating = sLow.includes("de-escalat") || sLow.includes("declin") || sLow.includes("fading");

      // Walk backward from Now based on trend direction
      const synthEarlier = (monthsBack)=>{
        const stepL = isEscalating ? -0.4 : isDeescalating ? +0.4 : 0;
        const stepI = isEscalating ? -0.3 : isDeescalating ? +0.3 : 0;
        const scale = Math.min(monthsBack/12, 1.5);
        return [
          Math.max(5, Math.min(10, nowPos[0] + stepL * scale)),
          Math.max(4, Math.min(10, nowPos[1] + stepI * scale)),
        ];
      };

      // 1. ORIGIN — earliest point
      if (originDt) {
        const monthsBack = Math.max(1, (Date.now() - originDt.getTime())/(30*86400000));
        const refPos = f.pos.jan25 || f.pos.jan26 || nowPos;
        const synthL = Math.max(5, Math.min(10, refPos[0] - Math.min(1.8, monthsBack*0.05)));
        const synthI = Math.max(4, Math.min(10, refPos[1] - Math.min(1.2, monthsBack*0.03)));
        const tooClose = Math.abs(synthL - nowPos[0]) < 0.3 && Math.abs(synthI - nowPos[1]) < 0.3;
        if (!tooClose) {
          const oLabel = originDt.toLocaleDateString("en-US",{month:"short",year:"numeric"});
          pts.push({label:`Origin · ${oLabel}`, pos:[synthL, synthI], kind:"origin", isSynthetic:true});
        }
      }

      // 2. JAN 2025 — real if available, synthesize if factor existed by then
      const existedByJan25 = !originDt || originDt <= jan25 || f.isFoundational;
      if (existedByJan25) {
        if (f.pos.jan25) {
          pts.push({label:"Jan 2025", pos:f.pos.jan25, kind:"anchor"});
        } else {
          const monthsBack = (Date.now() - jan25.getTime())/(30*86400000);
          pts.push({label:"Jan 2025 (est.)", pos:synthEarlier(monthsBack), kind:"anchor", isSynthetic:true});
        }
      }

      // 3. JAN 2026 — real if available, synthesize if factor existed by then
      const existedByJan26 = !originDt || originDt <= jan26 || f.isFoundational;
      if (existedByJan26) {
        if (f.pos.jan26) {
          pts.push({label:"Jan 2026", pos:f.pos.jan26, kind:"anchor"});
        } else {
          const monthsBack = (Date.now() - jan26.getTime())/(30*86400000);
          pts.push({label:"Jan 2026 (est.)", pos:synthEarlier(monthsBack), kind:"anchor", isSynthetic:true});
        }
      } else if (originDt && originDt > jan26) {
        const m = originDt.toLocaleDateString("en-US",{month:"short",year:"numeric"});
        pts.push({label:`Emerged ${m}`, pos:nowPos, kind:"emerged"});
      }

      // 4. NOW — always present; suppress if too close to last point
      if (nowPos) {
        const lastPt = pts[pts.length-1];
        const tooClose = lastPt && Math.abs(lastPt.pos[0]-nowPos[0])<0.2 && Math.abs(lastPt.pos[1]-nowPos[1])<0.2;
        if (!tooClose) pts.push({label:_nowMonth, pos:nowPos, kind:"now"});
      }

      return{f,pts};
    }).filter(Boolean);

    return(<div style={{display:"flex",gap:"14px",overflow:"hidden"}}>
      <div style={{flex:1,minWidth:0}}>
        <div style={{display:"flex",gap:"5px",marginBottom:"10px",flexWrap:"wrap",alignItems:"center"}}>
          {[["all","All"],["P","Political"],["E","Economic"],["S","Social"],["T","Tech"],["En","Environ."],["L","Legal"]].map(([k,l])=>(
            <button key={k} onClick={()=>{setV1Cat(k);setV1Sel(null);}} style={{padding:"4px 10px",borderRadius:"6px",border:`1px solid ${k===v1Cat?t.acc:t.border}`,background:k===v1Cat?`${t.acc}18`:t.btn,color:k===v1Cat?t.acc:t.c2,fontSize:"11px",fontWeight:600,cursor:"pointer"}}>{l}</button>
          ))}
          <span style={{width:1,height:20,background:t.border,margin:"0 4px"}}/>
          {[0,5,10,15,20].map(n=>(
            <button key={n} onClick={()=>setV1Top(n)} style={{padding:"4px 8px",borderRadius:"5px",border:`1px solid ${v1Top===n?t.acc:t.border}`,background:v1Top===n?`${t.acc}18`:t.btn,color:v1Top===n?t.acc:t.c2,fontSize:"10px",fontWeight:600,cursor:"pointer"}}>{n===0?"All":`Top ${n}`}</button>
          ))}
          {/* ── Historical lens — opt-in only; "Now" is implicit default ── */}
          <span style={{width:1,height:20,background:t.border,margin:"0 4px"}}/>
          <span style={{fontSize:"10px",color:t.c3,fontWeight:600,marginRight:"3px"}}>VIEW AS OF:</span>
          {v1Baseline==="now" ? (
            <span style={{fontSize:"10px",color:t.c2,fontStyle:"italic"}}>
              Current (live data, May 2026) — click below to rewind
            </span>
          ) : (
            <button onClick={()=>{setV1Baseline("now");setV1Sel(null);}}
              title="Return to current/live view"
              style={{padding:"4px 9px",borderRadius:"5px",border:`1px solid ${t.acc}`,
                background:`${t.acc}10`,color:t.acc,
                fontSize:"10px",fontWeight:600,cursor:"pointer"}}>← Back to Current</button>
          )}
          {[
            ["jan26","Jan 2026","Rewind to Jan 2026 — factors that emerged after this date will be hidden"],
            ["jan25","Jan 2025","Rewind to Jan 2025 — see the world as our analysts saw it 16 months ago"],
          ].map(([k,l,tip])=>(
            <button key={k} title={tip} onClick={()=>{setV1Baseline(k);setV1Sel(null);}}
              style={{padding:"4px 9px",borderRadius:"5px",border:`1px solid ${v1Baseline===k?t.acc:t.border}`,
                background:v1Baseline===k?`${t.acc}18`:t.btn,color:v1Baseline===k?t.acc:t.c2,
                fontSize:"10px",fontWeight:600,cursor:"pointer"}}>{l}</button>
          ))}
          {v1Baseline!=="now" && <span style={{fontSize:"9px",color:"#f59e0b",fontStyle:"italic",marginLeft:"4px"}}>
            ⚠ Historical view ({v1Baseline==="jan25"?"Jan 2025":"Jan 2026"}) — factors emerged after this date hidden. Trend symbols compare this baseline to the prior year.
          </span>}
          {isCompare&&<button onClick={()=>setV1Compare([])} style={{marginLeft:"auto",padding:"4px 10px",borderRadius:"5px",border:`1px solid ${t.acc}`,background:`${t.acc}18`,color:t.acc,fontSize:"10px",cursor:"pointer",fontWeight:600}}>✕ Exit Compare ({v1Compare.length})</button>}
        </div>

        {/* Empty-state when historical baseline shows zero factors */}
        {bubbles.length===0 && v1Baseline!=="now" && (
          <div style={{padding:"40px 20px",textAlign:"center",color:t.c3,fontSize:"12px",border:`1px dashed ${t.border}`,borderRadius:"8px",margin:"10px 0"}}>
            <div style={{fontSize:"24px",marginBottom:"8px"}}>○</div>
            <div style={{fontWeight:700,marginBottom:"4px"}}>No factors tracked at this baseline</div>
            <div>The system started tracking auto-component factors recently. Switch to "Now" or "Jan 2026" to see live data, or check back as historical depth grows.</div>
          </div>
        )}

        <div ref={svgRef} style={{...card(),padding:0,overflow:"hidden",minHeight:"460px",position:"relative"}}>
          <svg width={W} height={H} style={{display:"block"}}>
            {(()=>{const lkTicks=[];for(let _t=Math.ceil(lkMin);_t<=Math.floor(lkMax);_t++)lkTicks.push(_t);const impTicks=[];for(let _t=Math.ceil(impMin);_t<=Math.floor(impMax);_t++)impTicks.push(_t);const midLk=Math.round((lkMin+lkMax)/2);const midImp=Math.round((impMin+impMax)/2);return(<>{impTicks.map(v=><line key={`h${v}`} x1={pad.l} y1={sy(v)} x2={W-pad.r} y2={sy(v)} stroke={t.grid} strokeWidth={0.5} strokeDasharray={v===midImp?"none":"2,6"}/>)}{lkTicks.map(v=><line key={`vl${v}`} x1={sx(v)} y1={pad.t} x2={sx(v)} y2={H-pad.b} stroke={t.grid} strokeWidth={0.5} strokeDasharray={v===midLk?"none":"2,6"}/>)}{impTicks.map(v=><text key={`y${v}`} x={pad.l-8} y={sy(v)+4} fill={t.c3} fontSize="10" textAnchor="end">{v}</text>)}{lkTicks.map(v=><text key={`xl${v}`} x={sx(v)} y={H-pad.b+15} fill={t.c3} fontSize="10" textAnchor="middle">{v}</text>)}</>);})()}
            <text x={W/2} y={H-13} fill={t.c2} fontSize="11" textAnchor="middle" fontWeight="600">Likelihood →</text>
            <text x={W/2} y={H-3} fill={t.c3} fontSize="8" textAnchor="middle">How certain is this factor to materialise?</text>
            <text x={10} y={H/2} fill={t.c2} fontSize="11" textAnchor="middle" fontWeight="600" transform={`rotate(-90,10,${H/2})`}>Impact →</text>
            <text x={22} y={H/2} fill={t.c3} fontSize="7.5" textAnchor="middle" transform={`rotate(-90,22,${H/2})`}>Effect on ₹6.73L Cr auto component market</text>
            {/* Quadrant labels — background context, semi-transparent */}


            {(()=>{
              // V1 label repulsion
              const lbls=bubbles.map(b=>({id:b.id,x:b.cx,y:b.cy-b.r-6,w:Math.min(b.name.length,24)*5,h:10}));
              for(let pass=0;pass<40;pass++){for(let i=0;i<lbls.length;i++){for(let j=i+1;j<lbls.length;j++){
                const li=lbls[i],lj=lbls[j];
                const ox=Math.abs(li.x-lj.x),oy=Math.abs(li.y-lj.y);
                const minX=(li.w+lj.w)/2+4,minY=(li.h+lj.h)/2+2;
                if(ox<minX&&oy<minY){
                  const px=(minX-ox)*0.35*(li.x<lj.x?-1:1);
                  const py=(minY-oy)*0.55*(li.y<lj.y?-1:1);
                  lbls[i]={...lbls[i],x:lbls[i].x+px,y:lbls[i].y+py};
                  lbls[j]={...lbls[j],x:lbls[j].x-px,y:lbls[j].y-py};
                }
              }}}
              for(let i=0;i<lbls.length;i++){lbls[i].x=Math.max(pad.l+lbls[i].w/2,Math.min(W-pad.r-lbls[i].w/2,lbls[i].x));lbls[i].y=Math.max(pad.t+6,Math.min(H-pad.b-4,lbls[i].y));}
              return bubbles.map((b,idx)=>{const cc=CAT[b.cat].c;const isSel=v1Sel?.id===b.id;const inCmp=v1Compare.includes(b.id);const lb=lbls[idx];
              return <g key={b.id} style={{cursor:"pointer"}} onClick={()=>{if(isSel){setV1Sel(null);setAiAnalysis(null);}else{setV1Sel(b);if(b._from_api)fetchPestelAnalysis(b.id);}}} onContextMenu={e=>{e.preventDefault();setV1Compare(p=>p.includes(b.id)?p.filter(x=>x!==b.id):p.length>=3?p:[...p,b.id]);}}>
                <title>{b.name} (L:{b.lk} I:{b.imp} Score:{Math.round(b.lk*b.imp)})</title>
                <circle cx={b.cx} cy={b.cy} r={b.r} fill={`${cc}${dk?"30":"20"}`} stroke={`${cc}${isSel||inCmp?"":"70"}`} strokeWidth={isSel?2.5:inCmp?2:1} opacity={isCompare&&!inCmp?0.2:1}/>
                {(isSel||inCmp)&&<circle cx={b.cx} cy={b.cy} r={b.r+4} fill="none" stroke={cc} strokeWidth={1.5} opacity={0.5} strokeDasharray="3,3"/>}
                {(()=>{
                  // Trend glyph priority:
                  //   1. NEW badge if factor is new AND viewing "now"
                  //   2. Numeric delta if we have both pCur and pRef (real history)
                  //   3. Qualitative b.st string from LLM as fallback
                  //   4. ■ stable default
                  let glyph="\u25A0",gColor="#3b82f6",isNewBadge=false;
                  let pCur=null,pRef=null;
                  if(v1Baseline==="now"){
                    pCur=b.pos?.mar26||b.pos?.jan26;
                    pRef=b.pos?.jan26||b.pos?.jan25;
                  }else if(v1Baseline==="jan26"){
                    pCur=b.pos?.jan26;
                    pRef=b.pos?.jan25;
                  }else{
                    pCur=b.pos?.jan25;
                    pRef=null;
                  }
                  if(b.isNew && v1Baseline==="now"){
                    isNewBadge=true;
                  }else if(pCur && pRef){
                    // Numeric delta: have real history to compare
                    const s1=pRef[0]*pRef[1], s2=pCur[0]*pCur[1];
                    // Risk convention: ▲ RED = risk escalating (bad), ▼ GREEN = risk falling (good)
                    if(s2>s1*1.05){glyph="\u25B2"; gColor="#ef4444";}
                    else if(s2<s1*0.95){glyph="\u25BC"; gColor="#22c55e";}
                    else{glyph="\u25A0"; gColor="#3b82f6";}
                  }else if(v1Baseline==="now" && b.st){
                    // No history anchors — fall back to qualitative LLM trend string
                    const sLow = String(b.st).toLowerCase();
                    if(sLow.includes("escalat") || sLow.includes("acceler") || sLow.includes("rising") || sLow.includes("growing") || sLow.includes("upcoming")){
                      glyph="\u25B2"; gColor="#ef4444";
                    } else if(sLow.includes("de-escalat") || sLow.includes("declin") || sLow.includes("fading") || sLow.includes("decreas")){
                      glyph="\u25BC"; gColor="#22c55e";
                    } else {
                      glyph="\u25A0"; gColor="#3b82f6";
                    }
                  }
                  if(isNewBadge){
                    return(<g style={{pointerEvents:"none"}}>
                      <circle cx={b.cx+b.r*0.55} cy={b.cy-b.r*0.55} r={7} fill={dk?"#0a0e1a":"#ffffff"} stroke="#22c55e" strokeWidth={1.2}/>
                      <text x={b.cx+b.r*0.55} y={b.cy-b.r*0.55+3} fontSize="7" textAnchor="middle" fill="#22c55e" fontWeight="700">NEW</text>
                    </g>);
                  }
                  return(<g style={{pointerEvents:"none"}}>
                    <circle cx={b.cx+b.r*0.55} cy={b.cy-b.r*0.55} r={6} fill={dk?"#0a0e1a":"#ffffff"} stroke={gColor} strokeWidth={1}/>
                    <text x={b.cx+b.r*0.55} y={b.cy-b.r*0.55+3} fontSize="8" textAnchor="middle" fill={gColor} fontWeight="700">{glyph}</text>
                  </g>);
                })()}
                <line x1={b.cx} y1={b.cy-b.r} x2={lb.x} y2={lb.y+4} stroke={cc} strokeWidth={0.3} opacity={0.25}/>
                <text x={lb.x} y={lb.y} fill={cc} fontSize="8.5" fontWeight="600" textAnchor="middle" opacity={isCompare&&!inCmp?0.15:0.9} style={{pointerEvents:"none"}}>
                  {b.name.length>24?b.name.slice(0,22)+"…":b.name}
                </text>
              </g>;});
            })()}

            {isCompare&&compareData.map(({f,pts})=>{const cc=CAT[f.cat].c;
              const linePts = pts.filter(p => p.pos);
              return <g key={`t-${f.id}`}>
                {/* Trajectory polyline */}
                {linePts.length>1&&<polyline
                  points={linePts.map(p=>`${sx(p.pos[0])},${sy(p.pos[1])}`).join(" ")}
                  fill="none" stroke={cc} strokeWidth={2.5}
                  strokeDasharray="5,4" opacity={0.7}/>}
                {/* Each anchor */}
                {pts.map((p,i)=>{
                  if (!p.pos) return null;
                  const isOrigin = p.kind === "origin";
                  const isNow = p.kind === "now";
                  const isEmerged = p.kind === "emerged";
                  const cx = sx(p.pos[0]); const cy = sy(p.pos[1]);
                  return <g key={i}>
                    {/* Dashed ring for emerged markers */}
                    {isEmerged&&<circle cx={cx} cy={cy} r={10} fill="none"
                      stroke={cc} strokeWidth={1.2} strokeDasharray="2,3" opacity={0.6}/>}
                    {/* Origin: diamond (dashed outline) with ★ inside — synthetic */}
                    {isOrigin&&<g>
                      <polygon points={`${cx},${cy-7} ${cx+7},${cy} ${cx},${cy+7} ${cx-7},${cy}`}
                        fill={`${cc}20`} stroke={cc} strokeWidth={1.5} strokeDasharray="2,2"/>
                      <text x={cx} y={cy+3} fill={cc} fontSize="8" fontWeight="700" textAnchor="middle"
                        style={{pointerEvents:"none"}}>★</text>
                    </g>}
                    {/* Regular anchor or now — circle */}
                    {!isOrigin && <circle cx={cx} cy={cy}
                      r={isNow?7:5}
                      fill={isNow?cc:`${cc}28`}
                      stroke={cc}
                      strokeWidth={isNow?2:1.5}/>}
                    {/* Label */}
                    <text x={cx} y={cy-11} fill={cc} fontSize="9" fontWeight={isNow?700:600} textAnchor="middle">
                      {p.label}
                    </text>
                    {/* Synthetic sub-label for origin */}
                    {isOrigin&&<text x={cx} y={cy+18} fill={cc} fontSize="7"
                      fontStyle="italic" textAnchor="middle" opacity={0.7}>(estimated start)</text>}
                  </g>;
                })}
              </g>;})}
          </svg>
        </div>
        {isCompare && <div style={{display:"flex",gap:"10px",marginTop:"4px",marginBottom:"2px",justifyContent:"center",flexWrap:"wrap",alignItems:"center",fontSize:"9.5px",color:t.c2,padding:"4px 8px",background:`${t.acc}06`,borderRadius:"5px"}}>
          <span style={{fontWeight:700,color:t.c}}>TIMELINE ANCHORS:</span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}>
            <span style={{display:"inline-block",width:10,height:10,transform:"rotate(45deg)",border:`1.5px dashed ${t.c2}`,background:`${t.c2}20`}}/>
            <span>★ Origin (estimated start)</span>
          </span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}>
            <span style={{display:"inline-block",width:10,height:10,borderRadius:"50%",border:`1.5px solid ${t.c2}`,background:`${t.c2}28`}}/>
            <span>Jan 25 / Jan 26 (recorded snapshot)</span>
          </span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}>
            <span style={{display:"inline-block",width:10,height:10,borderRadius:"50%",border:`1.5px solid ${t.c2}`,background:`${t.c2}28`,outline:`1.5px dashed ${t.c2}`,outlineOffset:"2px"}}/>
            <span>Emerged YYYY (post Jan 26)</span>
          </span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}>
            <span style={{display:"inline-block",width:10,height:10,borderRadius:"50%",background:t.c2}}/>
            <span>Now (live)</span>
          </span>
        </div>}
        <div style={{display:"flex",gap:"10px",marginTop:"6px",justifyContent:"center",flexWrap:"wrap"}}>
          {Object.entries(CAT).map(([k,v])=><div key={k} style={{display:"flex",alignItems:"center",gap:"3px"}}><div style={{width:9,height:9,borderRadius:"50%",background:`${v.c}40`,border:`2px solid ${v.c}`}}/><span style={{fontSize:"9px",color:t.c2}}>{v.l}</span></div>)}
          <span style={{width:1,height:14,background:t.border,margin:"0 2px"}}/>
          <span title={"How to read the trend symbols:\n\n▲ Escalating — risk increased >5% vs prior baseline\n▼ Declining — risk decreased >5% vs prior baseline\n■ Stable — within ±5% of prior baseline\n🆕 New — factor emerged in last 90 days\n\nComparison rule:\n• Current view → compares to Jan 2026 snapshot\n• Jan 2026 view → compares to Jan 2025 snapshot\n• Jan 2025 view → no prior (all ■)\n\nWhen DB snapshots are missing, the AI's qualitative trend tag (Escalating/Declining/Stable) is used. Trajectory anchors marked '(est.)' are synthesized from the trend direction."} style={{fontSize:"9px",color:t.acc,fontStyle:"italic",cursor:"help",marginRight:"4px",fontWeight:600,padding:"2px 6px",borderRadius:"4px",background:`${t.acc}10`,border:`1px solid ${t.acc}30`}}>
            ⓘ How to read trend symbols
          </span>
          <span style={{fontSize:"9px",color:t.c2,fontWeight:600}}>TREND vs prior baseline:</span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}><span style={{color:"#ef4444",fontWeight:700,fontSize:11}}>▲</span><span style={{fontSize:"9px",color:t.c2}}>Escalating risk</span></span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}><span style={{color:"#3b82f6",fontWeight:700,fontSize:11}}>■</span><span style={{fontSize:"9px",color:t.c2}}>Stable</span></span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}><span style={{color:"#22c55e",fontWeight:700,fontSize:11}}>▼</span><span style={{fontSize:"9px",color:t.c2}}>Declining risk</span></span>
          <span style={{display:"inline-flex",alignItems:"center",gap:"3px"}}><span style={{color:"#22c55e",fontWeight:700,fontSize:9,padding:"1px 4px",border:"1px solid #22c55e",borderRadius:6}}>NEW</span></span>
          <span style={{fontSize:"9px",color:t.c3,marginLeft:"6px"}}>Size=Risk · Click=details · Right-click=compare</span>
        </div>
      </div>

      {v1Sel&&(()=>{const f=v1Sel;const cc=CAT[f.cat].c;const p=f.pos.mar26||f.pos.jan26;const score=p?Math.round(p[0]*p[1]*10)/10:null;
        const note=f.segNote?.[seg]||f.segNote?.[Object.keys(f.segNote||{})[0]]||f.desc;
        const _nowLabel = new Date().toLocaleDateString("en-US", {month: "short", year: "numeric"}) + " (Now)";
        const tl=[{k:"jan25",l:"Jan 2025"},{k:"jan26",l:"Jan 2026"},{k:"mar26",l:_nowLabel}];
        const td=(()=>{
          const j26=f.pos.jan26,m26=f.pos.mar26;
          // Prefer numeric delta when both anchors exist
          if(j26 && m26){
            const s1=j26[0]*j26[1],s2=m26[0]*m26[1];
            if(s2>s1*1.05) return "escalating";
            if(s2<s1*0.95) return "de-escalating";
            return "stable";
          }
          // Fall back to LLM qualitative tag
          const sLow = String(f.st||f.trend||"").toLowerCase();
          if(sLow.includes("escalat") || sLow.includes("acceler") || sLow.includes("rising") || sLow.includes("growing") || sLow.includes("upcoming")) return "escalating";
          if(sLow.includes("de-escalat") || sLow.includes("declin") || sLow.includes("fading") || sLow.includes("decreas")) return "de-escalating";
          return "stable";
        })();
        const rl=score>=70?"Critical":score>=50?"High":score>=30?"Moderate":"Low";
        const affPils=f.pil||[];
        const relTechs=affPils.flatMap(pid=>TECHS.filter(tt=>tt.p===pid&&isTechRelevantForSegment(tt,seg))).slice(0,5);
        const totalMkt=relTechs.reduce((s,tt)=>s+tt.sz[seg],0);
        // Financial context
        const indSize=673000;// ₹6.73L Cr
        const mktImpactPct=totalMkt>0?((totalMkt/indSize)*100).toFixed(2):"—";
        return <div style={{width:"360px",flexShrink:0,overflowY:"auto",maxHeight:"680px",...card()}}>
          <div style={{display:"flex",alignItems:"center",gap:"5px",marginBottom:"6px"}}>
            <div style={{width:9,height:9,borderRadius:"50%",background:cc}}/><span style={{fontSize:"10px",color:cc,fontWeight:700}}>{CAT[f.cat].l.toUpperCase()} · {SEGS[seg].s}</span>
            {f.isNew&&<span style={{fontSize:"8px",padding:"2px 5px",borderRadius:"3px",background:"#22c55e18",color:"#22c55e",fontWeight:600}}>NEW</span>}
            {(()=>{
              const tier=f.freshnessTier||(f.isFoundational?"ESTABLISHED":"EMERGING");
              const cfg={
                FRESH:      {label:"FRESH",      bg:"#22c55e18",color:"#22c55e", tip:"Mentioned in source news within last 7 days"},
                ESTABLISHED:{label:"CONFIRMED",  bg:"#3b82f618",color:"#3b82f6", tip:"Confirmed across 3+ refresh cycles or marked as foundational"},
                EMERGING:   {label:"EMERGING",   bg:"#f59e0b18",color:"#f59e0b", tip:"Recently surfaced; not yet repeated across multiple sources"},
                DECAYING:   {label:"DECAYING",   bg:"#ef444418",color:"#ef4444", tip:"Single source, no re-mention in 14+ days"},
                FADING:     {label:"FADING",     bg:"#78716c18",color:"#78716c", tip:"No fresh news mentions in 30+ days. Note: this is about news cadence, NOT whether the factor is escalating/declining strategically \u2014 those are shown in the trend chip below."},
              }[tier]||{label:tier,bg:"#ffffff10",color:"#aaa", tip:""};
              return <span title={cfg.tip} style={{fontSize:"8px",padding:"2px 5px",borderRadius:"3px",background:cfg.bg,color:cfg.color,fontWeight:600,marginLeft:"2px",cursor:"help"}}>{cfg.label}</span>;
            })()}
          </div>
          <h3 style={{margin:"0 0 5px",fontSize:"15px",fontWeight:700,color:t.c}}>{f.name}</h3>
          <div style={{fontSize:"11px",color:t.c2,lineHeight:1.5,marginBottom:"8px"}}>{f.desc}</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:"4px",marginBottom:"8px"}}>
            {[["Likelihood",p?p[0]:"—",null],["Impact",p?p[1]:"—",null],["Risk Score",score||"—",cc]].map(([l,v,c],i)=>
              <div key={i} style={{padding:"5px",background:c?`${c}10`:t.btn,borderRadius:"6px",textAlign:"center",border:c?`1px solid ${c}25`:"none"}}>
                <div style={{fontSize:"8px",color:c||t.c3}}>{l}</div><div style={{fontSize:"15px",fontWeight:700,color:c||t.c}}>{v}</div>
              </div>)}
          </div>
          <div style={{display:"flex",gap:"3px",marginBottom:"8px",flexWrap:"wrap"}} title="Trend computed from L×I score change vs Jan 2026 baseline. >5% increase = Escalating, <-5% = De-escalating, else Stable.">
            <span style={{fontSize:"9px",padding:"2px 6px",borderRadius:"4px",background:rl==="Critical"?"#ef444415":rl==="High"?"#f9731615":"#3b82f615",color:rl==="Critical"?"#ef4444":rl==="High"?"#f97316":"#3b82f6",fontWeight:600}}>{rl} Risk</span>
            <span style={{fontSize:"9px",padding:"2px 6px",borderRadius:"4px",background:td==="escalating"?"#ef444415":td==="de-escalating"?"#22c55e15":"#64748b15",color:td==="escalating"?"#ef4444":td==="de-escalating"?"#22c55e":"#64748b",fontWeight:600}}>{td==="escalating"?"↑ Escalating (vs Jan 2026)":td==="de-escalating"?"↓ De-escalating (vs Jan 2026)":"→ Stable (vs Jan 2026)"}</span>
          </div>

          <div style={{padding:"6px 8px",marginBottom:"6px",fontSize:"11px",color:td==="escalating"?"#ef4444":td==="de-escalating"?"#22c55e":t.c3,fontWeight:600}}>
            <strong style={{color:t.c}}>Strategic Implication:</strong>{" "}
            {td==="escalating"?`Risk escalating — L×I score ${f.pos.jan26?`moved from ${Math.round(f.pos.jan26[0]*f.pos.jan26[1])} to `:"now "}${score}. Active contingency planning required for ${SEGS[seg].l}.`
            :td==="de-escalating"?`Risk declining — score ${f.pos.jan26?`decreased from ${Math.round(f.pos.jan26[0]*f.pos.jan26[1])} to `:"now "}${score}. Risk reducing for ${SEGS[seg].l}.`
            :td==="emerging"?`Newly emerged factor. Building trajectory data. Monitor closely for ${SEGS[seg].l} impact.`
            :`Score stable at ${score}. Maintain current positioning for ${SEGS[seg].l}.`}
          </div>

          <div style={{padding:"8px",borderRadius:"8px",background:t.btn,marginBottom:"8px"}}>
            <div style={{fontSize:"10px",color:t.acc,fontWeight:700,marginBottom:"3px"}}>◆ FINANCIAL OVERLAY · {SEGS[seg].s}</div>
            <div style={{fontSize:"11px",color:t.c2,lineHeight:1.55}}>
              Technology market directly affected: <strong style={{color:t.c}}>{fmt(totalMkt)}</strong> ({mktImpactPct}% of ₹6.73L Cr industry).
              {score>=60?` High risk score of ${score} signals potential disruption to ${relTechs.length} technology areas.`
              :` Moderate exposure — ${relTechs.length} technology areas impacted at manageable risk levels.`}
            </div>
          </div>

          {relTechs.length>0&&<div style={{marginBottom:"8px"}}>
            <div style={{fontSize:"10px",color:t.c3,fontWeight:600,marginBottom:"3px"}}>AFFECTED TECHNOLOGIES · {fmt(totalMkt)}</div>
            {relTechs.map((tt,i)=>{const pl=PM[tt.p];return <div key={i} style={{display:"flex",alignItems:"center",gap:"3px",padding:"2px 0",fontSize:"10px"}}>
              <div style={{width:3,height:12,borderRadius:1,background:pl?.color,flexShrink:0}}/><span style={{color:t.c,flex:1}}>{tt.n}</span><span style={{color:t.c2}}>{fmt(tt.sz[seg])}</span><span style={{color:pl?.color,fontWeight:600,minWidth:"30px",textAlign:"right"}}>{tt.cagr}%</span>
            </div>;})}
          </div>}

          <div style={{fontSize:"10px",color:t.c3,fontWeight:600,marginBottom:"3px"}}>TIMELINE</div>
          {f.origin&&<div style={{padding:"5px 7px",borderRadius:"4px",background:`${t.acc}08`,border:`1px solid ${t.acc}15`,marginBottom:"3px",display:"flex",justifyContent:"space-between",fontSize:"10px"}}>
            <span style={{fontWeight:600,color:t.acc}}>Origin</span>
            <span style={{color:t.c2,textAlign:"right",maxWidth:"200px"}}>{f.origin}</span>
          </div>}
          {tl.map(ti=>{const pos=f.pos[ti.k];
            if(!pos){
              // Honest message: factor either didn't exist yet, or no snapshot was recorded
              const originDt = f.originDate ? new Date(f.originDate) : null;
              const refLabel = ti.k==="jan25" ? new Date("2025-01-15") : new Date("2026-01-15");
              const isPreOrigin = originDt && originDt > refLabel;
              const msg = isPreOrigin
                ? `${ti.l} — factor had not yet emerged (origin: ${f.origin || "later"})`
                : `${ti.l} — no snapshot recorded`;
              return <div key={ti.k} style={{padding:"4px 7px",borderRadius:"4px",background:isPreOrigin?`${t.acc}06`:t.btn,opacity:0.6,marginBottom:"2px",fontSize:"10px",color:t.c3,fontStyle:"italic"}}>
                <span style={{marginRight:4}}>{isPreOrigin?"○":"·"}</span>{msg}
              </div>;
            }
            const sc=Math.round(pos[0]*pos[1]*10)/10;
            return <div key={ti.k} style={{padding:"4px 7px",borderRadius:"4px",background:ti.k==="mar26"?`${cc}08`:t.btn,border:ti.k==="mar26"?`1px solid ${cc}20`:"1px solid transparent",marginBottom:"2px",display:"flex",justifyContent:"space-between",fontSize:"10px"}}>
              <span style={{fontWeight:ti.k==="mar26"?700:400,color:ti.k==="mar26"?t.c:t.c2}}>{ti.l}</span>
              <span style={{color:t.c2}}>L:{pos[0]} I:{pos[1]} <strong style={{color:cc}}>{sc}</strong></span>
            </div>;})}
          <div style={{fontSize:"9px",color:t.c3,marginTop:"6px"}}>Source: {f.src}</div>
          {aiLoading&&<div style={{padding:"12px",textAlign:"center",color:t.c3,fontSize:"11px"}}>⏳ Generating AI analysis via Claude Sonnet 4.6...</div>}
          {aiAnalysis&&!aiLoading&&<div style={{marginTop:"10px",padding:"12px",borderRadius:"8px",border:`1px solid ${t.border}`,background:`${t.acc}05`}}>
            {/* Summary */}
            {(aiAnalysis.summary||aiAnalysis.strategic_outlook)&&(
              <div style={{fontSize:"11px",color:t.c,lineHeight:"1.6",marginBottom:"10px"}}>{aiAnalysis.summary||aiAnalysis.strategic_outlook}</div>
            )}
            {/* Financial Overlay */}
            {aiAnalysis.financial_overlay&&(()=>{const fo=aiAnalysis.financial_overlay;const rows=Object.entries(fo).filter(([,v])=>v&&v!=="N/A");return rows.length>0?(
              <div style={{marginBottom:"10px",padding:"8px",borderRadius:"6px",background:`${t.acc}0a`,border:`1px solid ${t.acc}20`}}>
                <div style={{fontSize:"9px",fontWeight:700,color:t.acc,marginBottom:"5px",letterSpacing:"0.05em"}}>◆ FINANCIAL CONTEXT</div>
                {rows.map(([k,v])=>(
                  <div key={k} style={{display:"flex",justifyContent:"space-between",fontSize:"10px",marginBottom:"2px"}}>
                    <span style={{color:t.c3,textTransform:"capitalize"}}>{k.replace(/_/g," ")}</span>
                    <span style={{color:t.c,fontWeight:600,maxWidth:"55%",textAlign:"right"}}>{v}</span>
                  </div>
                ))}
              </div>
            ):null;})()}
            {/* Key Dates */}
            {aiAnalysis.key_dates&&(()=>{const kd=aiAnalysis.key_dates;const chips=Object.entries(kd).filter(([,v])=>v&&v.length>0);return chips.length>0?(
              <div style={{display:"flex",flexWrap:"wrap",gap:"4px",marginBottom:"10px"}}>
                {chips.map(([k,v])=>(
                  <span key={k} style={{fontSize:"9px",padding:"2px 7px",borderRadius:"10px",background:`${t.acc}18`,color:t.acc,fontWeight:600}}>
                    {k.replace(/_/g," ")}: {v}
                  </span>
                ))}
              </div>
            ):null;})()}
            {/* Strategic Options */}
            {(aiAnalysis.strategic_options||aiAnalysis.bosch_action)&&(
              <div style={{marginBottom:"10px"}}>
                <div style={{fontSize:"9px",fontWeight:700,color:t.acc,marginBottom:"4px",letterSpacing:"0.04em"}}>STRATEGIC OPTIONS</div>
                {(aiAnalysis.strategic_options||aiAnalysis.bosch_action).map((a,i)=>(
                  <div key={i} style={{fontSize:"10px",color:t.c2,padding:"3px 8px",borderLeft:`2px solid ${t.acc}50`,marginBottom:"3px",lineHeight:"1.45"}}>{a}</div>
                ))}
              </div>
            )}
            {/* Citations */}
            {aiAnalysis.citations&&aiAnalysis.citations.length>0&&(
              <div style={{marginBottom:"8px"}}>
                <div style={{fontSize:"9px",fontWeight:700,color:t.c3,marginBottom:"3px",letterSpacing:"0.04em"}}>CITATIONS</div>
                {aiAnalysis.citations.slice(0,3).map((c2,i)=>(
                  <div key={i} style={{fontSize:"9px",color:t.c3,lineHeight:"1.4",marginBottom:"2px"}}>
                    <span style={{fontWeight:600,color:t.c2}}>[{i+1}]</span> {typeof c2==="object"?`${c2.claim} — ${c2.source}`:c2}
                  </div>
                ))}
              </div>
            )}
            {/* Model attribution */}
            <div style={{fontSize:"9px",color:t.c3,borderTop:`1px solid ${t.border}`,paddingTop:"6px",marginTop:"4px"}}>
              {aiAnalysis._meta?.model||"claude-sonnet-4-6"}{aiAnalysis._meta?.generated_at&&` · ${new Date(aiAnalysis._meta.generated_at).toLocaleString()}`}{aiAnalysis._from_cache&&" · ⚡ cached"}
            </div>
          </div>}
          <button onClick={()=>{if(v1Compare.length<3){setV1Compare(p=>[...p,f.id]);setV1Sel(null);setAiAnalysis(null);}}} title={v1Compare.length>=3?"Compare is capped at 3 factors — click Exit Compare to reset":"Right-click any bubble to add to compare"} style={{marginTop:"8px",width:"100%",padding:"6px",borderRadius:"6px",border:`1px solid ${v1Compare.length>=3?t.border:t.acc}40`,background:v1Compare.length>=3?t.btn:`${t.acc}08`,color:v1Compare.length>=3?t.c3:t.acc,fontSize:"10px",fontWeight:600,cursor:v1Compare.length>=3?"not-allowed":"pointer",opacity:v1Compare.length>=3?0.5:1}}>{v1Compare.length>=3?"Compare full (3/3) — Exit Compare to reset":"+ Add to Timeline Compare"}</button>
        </div>;})()}
    </div>);
  };

  /* ═══ VIEW 2: BOSCH TECH STACK ═══ */
  const renderV2=()=>{
    const layers=[[0,"Application & Digital Services"],[1,"Vehicle Functions"],[2,"Software Platform"],[3,"Hardware Foundation"]];
    const selP=v2Pil?PM[v2Pil]:null;
    const pilForces=v2Pil?PESTEL.filter(f=>f.pil.includes(v2Pil)&&isPestelRelevantForSegment(f,seg)).sort((a,b)=>(b.rel[seg]==="H"?1:0)-(a.rel[seg]==="H"?1:0)):[];
    const indirectForces=v2Pil?PESTEL.filter(f=>!f.pil.includes(v2Pil)&&isPestelRelevantForSegment(f,seg)&&(f.rel[seg]||"L")==="H").sort((a,b)=>{const pa=a.pos.mar26||a.pos.jan26||[0,0];const pb=b.pos.mar26||b.pos.jan26||[0,0];return(pb[0]*pb[1])-(pa[0]*pa[1]);}).slice(0,5):[];
    const pilTechs=v2Pil?TECHS.filter(t=>t.p===v2Pil&&isTechRelevantForSegment(t,seg)).sort((a,b)=>(b.sz[seg]*b.cagr)-(a.sz[seg]*a.cagr)):[];
    const layerColors=["#64748b","#3b82f6","#7c3aed","#475569"];

    return(<div style={{display:"flex",gap:"12px",overflow:"hidden"}}>
      {/* Left: PESTEL forces with mini chart */}
      {v2Pil&&<div style={{width:"280px",flexShrink:0,overflowY:"auto",maxHeight:"640px",...card()}}>
        <div style={{fontSize:"11px",color:t.c3,fontWeight:600,marginBottom:"6px"}}>PESTEL FORCES → {selP?.label?.toUpperCase()}</div>
        <div style={{fontSize:"10px",color:t.c3,marginBottom:"8px"}}>{pilForces.length} direct · {indirectForces.length} indirect for {SEGS[seg].s}</div>
        {/* Mini bubble chart for forces */}
        <div style={{height:"120px",background:t.btn,borderRadius:"8px",marginBottom:"10px",position:"relative",overflow:"hidden"}}>
          <svg width="100%" height="100%" viewBox="0 0 260 110" preserveAspectRatio="xMidYMid meet">
            {pilForces.map((f,i)=>{const cc=CAT[f.cat].c;const p=f.pos.mar26||f.pos.jan26;if(!p)return null;
              const cx=20+((p[0]-1)/9)*220,cy=100-((p[1]-1)/9)*85,r=Math.max(5,Math.min(14,4+p[0]*p[1]/10));
              return <g key={f.id}><circle cx={cx} cy={cy} r={r} fill={`${cc}30`} stroke={cc} strokeWidth={1.2}/>
                <text x={cx} y={cy-r-3} fill={cc} fontSize="6.5" fontWeight="600" textAnchor="middle">{f.name.slice(0,16)}</text></g>;})}
            <text x="130" y="108" fill={t.c3} fontSize="6" textAnchor="middle">Likelihood →</text>
            <text x="5" y="50" fill={t.c3} fontSize="6" textAnchor="middle" transform="rotate(-90,5,50)">Impact →</text>
          </svg>
        </div>
        {/* Direct forces */}
        {pilForces.length>0&&<div style={{fontSize:"9px",color:t.c3,fontWeight:700,marginBottom:"4px",letterSpacing:"0.05em"}}>◉ DIRECT ({pilForces.length})</div>}
        {pilForces.map(f=>{const cc=CAT[f.cat].c;const rl=f.rel[seg];const p=f.pos.mar26||f.pos.jan26;
          return <div key={f.id} style={{padding:"8px",marginBottom:"4px",borderRadius:"7px",background:`${cc}08`,borderLeft:`3px solid ${cc}50`}}>
            <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"2px",gap:"4px"}}>
              <span style={{fontSize:"8px",padding:"1px 4px",borderRadius:"3px",background:`${cc}18`,color:cc,fontWeight:700,flexShrink:0}}>{CAT[f.cat].l.charAt(0)}</span>
              <span style={{fontSize:"11px",fontWeight:600,color:t.c,flex:1}}>{f.name.length>24?f.name.slice(0,22)+"…":f.name}</span>
              <span style={{fontSize:"8px",padding:"1px 4px",borderRadius:"3px",background:rl==="H"?"#ef444415":"#eab30815",color:rl==="H"?"#ef4444":"#eab308",fontWeight:600}}>{rl}</span>
            </div>
            {p&&<div style={{fontSize:"9px",color:t.c3}}>L:{p[0]} I:{p[1]} Score:<strong style={{color:cc}}>{Math.round(p[0]*p[1])}</strong></div>}
            <div style={{fontSize:"10px",color:t.c2,marginTop:"2px",lineHeight:1.3}}>{(f.segNote?.[seg]||f.desc).slice(0,80)}…</div>
          </div>;})}
        {/* Indirect high-impact forces */}
        {indirectForces.length>0&&<><div style={{fontSize:"9px",color:t.c3,fontWeight:700,margin:"6px 0 4px",letterSpacing:"0.05em"}}>◎ INDIRECT · HIGH IMPACT ({indirectForces.length})</div>
        {indirectForces.map(f=>{const cc=CAT[f.cat].c;const p=f.pos.mar26||f.pos.jan26;
          return <div key={f.id} style={{padding:"7px",marginBottom:"3px",borderRadius:"7px",background:`${cc}05`,borderLeft:`2px solid ${cc}35`,opacity:0.85}}>
            <div style={{display:"flex",alignItems:"center",gap:"4px",marginBottom:"2px"}}>
              <span style={{fontSize:"8px",padding:"1px 4px",borderRadius:"3px",background:`${cc}15`,color:cc,fontWeight:700,flexShrink:0}}>{CAT[f.cat].l.charAt(0)}</span>
              <span style={{fontSize:"10px",fontWeight:600,color:t.c2,flex:1}}>{f.name.length>24?f.name.slice(0,22)+"…":f.name}</span>
            </div>
            {p&&<div style={{fontSize:"9px",color:t.c3}}>Score:<strong style={{color:cc}}>{Math.round(p[0]*p[1])}</strong></div>}
          </div>;})}
        </>}
      </div>}

      {/* Center: Bosch Stack — proper architectural SVG structure */}
      <div style={{flex:1,minWidth:0}}>
        <div style={{fontSize:"11px",color:t.c3,fontWeight:600,marginBottom:"6px",textAlign:"center",letterSpacing:"0.05em"}}>BOSCH MOBILITY SOLUTIONS — TECHNOLOGY STACK · {SEGS[seg].s}</div>
        {(()=>{
          // ── Wider canvas to accommodate icon callouts on both sides ──
          const W=900,H2=520;
          const isSel=(pid)=>v2Pil===pid;
          const pCol=(pid)=>PM[pid]?.color||"#666";
          const clickP=(pid)=>()=>setV2Pil(isSel(pid)?null:pid);
          const bg2=dk?"#0f172a":"#f0f4f8";
          const bd2=dk?"#1e3a5f":"#b0c4de";
          const blue=dk?"#1e40af":"#185FA5";
          const teal=dk?"#0d9488":"#0F6E56";
          const purple=dk?"#7c3aed":"#534AB7";
          const txt=t.c;const txt2=t.c2;

          // CAGR-driven dot color (kept from original logic)
          const getPillarDotColor=(pid)=>{
            const pts=TECHS.filter(tt=>tt.p===pid&&(tt.sz[seg]||0)>0);
            if(!pts.length)return"#64748b";
            const totalSz=pts.reduce((s,tt)=>s+(tt.sz[seg]||0),0);
            if(!totalSz)return"#64748b";
            const wCagr=pts.reduce((s,tt)=>s+tt.cagr*(tt.sz[seg]||0),0)/totalSz;
            return wCagr>=15?"#22c55e":wCagr>=5?"#f59e0b":wCagr>=0?"#3b82f6":"#ef4444";
          };

          // ── Pillar renderer: CAGR dot + label + market size ──
          const rpil=(pid,x,y,w,h)=>{
            const s=isSel(pid);
            const c=pCol(pid);
            const dc=getPillarDotColor(pid);
            // Compute market size for this pillar in current segment
            const techsForP = TECHS.filter(tt=>tt.p===pid && (tt.sz?.[seg]||0)>0);
            const totalSz = techsForP.reduce((sum,tt)=>sum+(tt.sz[seg]||0),0);
            const sizeText = totalSz>0 ? fmt(totalSz, curr) : "";
            return <g key={pid} onClick={clickP(pid)} style={{cursor:"pointer"}}>
              <rect x={x} y={y} width={w} height={h} rx={4}
                fill={s?`${c}25`:dk?"#1e293b":"#ffffff"}
                stroke={s?c:bd2} strokeWidth={s?2:1}/>
              {/* CAGR dot top-center */}
              <circle cx={x+w/2} cy={y+10} r={3.5} fill={dc}/>
              {/* Pillar name in middle */}
              <text x={x+w/2} y={y+h/2+1} fill={s?c:txt} fontSize="11" fontWeight="700" textAnchor="middle">
                {PM[pid]?.label}
              </text>
              {/* Market size below name — only if non-zero */}
              {sizeText && <text x={x+w/2} y={y+h-7} fill={s?c:txt2} fontSize="8.5" fontWeight="600" textAnchor="middle" opacity={0.85}>
                {sizeText}
              </text>}
            </g>;
          };

          // Center stack X offset (leaves room for left/right callouts)
          const stackX=200, stackW=500;

          // ── Icon callout renderer ──
          const callout=(pos, y, label, sublabel, accent)=>{
            const cx = pos==="left" ? 95 : W-95;
            const tx = pos==="left" ? 130 : W-130;
            const lx = pos==="left" ? stackX : stackX+stackW;
            return <g key={`${pos}-${y}-${label}`}>
              <line x1={cx+(pos==="left"?20:-20)} y1={y} x2={lx} y2={y}
                stroke={bd2} strokeWidth={0.6} strokeDasharray="2,3" opacity={0.5}/>
              <circle cx={cx} cy={y} r={18} fill={dk?"#1e293b":"#ffffff"} stroke={accent||bd2} strokeWidth={1.2}/>
              <circle cx={cx} cy={y} r={14} fill={accent?`${accent}20`:`${bd2}30`} stroke="none"/>
              <text x={tx} y={y-2} fill={txt} fontSize="8" fontWeight="600"
                textAnchor={pos==="left"?"end":"start"}>{label}</text>
              <text x={tx} y={y+8} fill={txt2} fontSize="6.5"
                textAnchor={pos==="left"?"end":"start"}>{sublabel}</text>
            </g>;
          };

          // ── Helper: render CAGR dot + market size INSIDE any band ──
          const bandInfo=(pid,x,y,w,h,labelColor,fontSize)=>{
            const techsForP = TECHS.filter(tt=>tt.p===pid && (tt.sz?.[seg]||0)>0);
            const totalSz = techsForP.reduce((s,tt)=>s+(tt.sz[seg]||0),0);
            const dc = getPillarDotColor(pid);
            return <g style={{pointerEvents:"none"}}>
              {/* CAGR dot inside band, top-left */}
              <circle cx={x+11} cy={y+10} r={3.5} fill={dc} stroke="#ffffff" strokeWidth={0.8}/>
              {/* Market size on the right side */}
              {totalSz>0 && <text x={x+w-8} y={y+12} fill="#ffffff" fontSize={fontSize||"9"} fontWeight="600" textAnchor="end" opacity={0.92}>
                {fmt(totalSz, curr)}
              </text>}
            </g>;
          };

          // ── Wider X for wrapping bands (like Bosch reference) ──
          const wrapPad = 14;
          const outerX = stackX - wrapPad;
          const outerW = stackW + 2*wrapPad;

          return <>
          {/* ── Selection header above diagram ── */}
          <div style={{textAlign:"center",fontSize:"12px",fontWeight:700,color:v2Pil?PM[v2Pil]?.color:t.c2,marginBottom:"6px",letterSpacing:"0.04em",minHeight:"18px"}}>
            {v2Pil ? <>SELECTED: <span style={{color:PM[v2Pil]?.color}}>{PM[v2Pil]?.label}</span> · {SEGS[seg]?.s}</>
                   : <span style={{color:t.c3,fontWeight:500,fontStyle:"italic"}}>Click any layer to filter PESTEL forces and growth drivers · {SEGS[seg]?.s}</span>}
          </div>

          <svg width="100%" viewBox={`0 0 ${W} ${H2}`} style={{display:"block",maxHeight:"560px"}}>

            {/* ─── ROOF / SOLUTIONS BUSINESS ─── */}
            <g onClick={clickP("Solutions")} style={{cursor:"pointer"}}>
              <polygon points={`${stackX+stackW/2},10 ${outerX+10},58 ${outerX+outerW-10},58`}
                fill={isSel("Solutions")?`${blue}25`:"transparent"}
                stroke={blue} strokeWidth={isSel("Solutions")?3:2.5} opacity={0.85}/>
              <text x={stackX+stackW/2} y={42} fill={blue} fontSize="13" fontWeight="700" textAnchor="middle">Solutions business</text>
              {(()=>{
                const techsForP = TECHS.filter(tt=>tt.p==="Solutions" && (tt.sz?.[seg]||0)>0);
                const totalSz = techsForP.reduce((s,tt)=>s+(tt.sz[seg]||0),0);
                if(totalSz<=0) return null;
                return <text x={stackX+stackW/2} y={54} fill={blue} fontSize="9" fontWeight="600" textAnchor="middle" opacity={0.85}>{fmt(totalSz, curr)}</text>;
              })()}
            </g>

            {/* ─── SERVICES BAND (wraps wider than inner pillars) ─── */}
            <g onClick={clickP("Services")} style={{cursor:"pointer"}}>
              <rect x={outerX} y={62} width={outerW} height={36} rx={3}
                fill={blue} opacity={isSel("Services")?1:0.85}
                stroke={isSel("Services")?"#ffffff":"none"} strokeWidth={isSel("Services")?2:0}/>
              <text x={stackX+stackW/2} y={85} fill="#ffffff" fontSize="13" fontWeight="700" textAnchor="middle">Services</text>
              {bandInfo("Services",outerX,62,outerW,36)}
            </g>

            {/* ─── OS CLOUD / BACKEND INTERFACE ─── */}
            <g onClick={clickP("Cloud")} style={{cursor:"pointer"}}>
              <rect x={outerX} y={102} width={outerW} height={28} rx={3}
                fill={teal} opacity={isSel("Cloud")?1:0.85}
                stroke={isSel("Cloud")?"#ffffff":"none"} strokeWidth={isSel("Cloud")?2:0}/>
              <text x={stackX+stackW/2} y={121} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">OS cloud / backend interface</text>
              {bandInfo("Cloud",outerX,102,outerW,28)}
            </g>

            {/* ─── VEHICLE FUNCTIONS row — sits INSIDE the wrapping bands ─── */}
            <rect x={stackX} y={134} width={stackW} height={70} rx={3}
              fill={dk?"#1e3a5f":"#dbeafe"} opacity={0.4}/>
            {rpil("ADAS",       stackX+5,   140, 96, 56)}
            {rpil("Motion",     stackX+106, 140, 96, 56)}
            {rpil("Energy",     stackX+207, 140, 96, 56)}
            {rpil("Body & Comfort", stackX+308, 140, 96, 56)}
            {rpil("Infotainment", stackX+409, 140, 86, 56)}

            {/* ─── APPLICATION SOFTWARE ─── */}
            <g onClick={clickP("OS")} style={{cursor:"pointer"}}>
              <rect x={outerX} y={208} width={outerW} height={28} rx={3}
                fill={teal} opacity={isSel("OS")?1:0.85}
                stroke={isSel("OS")?"#ffffff":"none"} strokeWidth={isSel("OS")?2:0}/>
              <text x={stackX+stackW/2} y={227} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">Application software</text>
              {bandInfo("OS",outerX,208,outerW,28)}
            </g>

            {/* ─── OPERATING SYSTEM ─── */}
            <g onClick={clickP("Solutions")} style={{cursor:"pointer"}}>
              <rect x={outerX} y={240} width={outerW} height={28} rx={3}
                fill={teal} opacity={isSel("Solutions")?1:0.7}
                stroke={isSel("Solutions")?"#ffffff":"none"} strokeWidth={isSel("Solutions")?2:0}/>
              <text x={stackX+stackW/2} y={259} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">Operating system</text>
              {bandInfo("Solutions",outerX,240,outerW,28)}
            </g>

            {/* ─── COMPUTE ─── */}
            <g onClick={clickP("Compute")} style={{cursor:"pointer"}}>
              <rect x={stackX} y={272} width={stackW} height={26} rx={3}
                fill={purple} opacity={isSel("Compute")?1:0.85}
                stroke={isSel("Compute")?"#ffffff":"none"} strokeWidth={isSel("Compute")?2:0}/>
              <text x={stackX+stackW/2} y={290} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">Compute</text>
              {bandInfo("Compute",stackX,272,stackW,26)}
            </g>

            {/* ─── EMBEDDED ECUs ─── */}
            <g onClick={clickP("ECUs")} style={{cursor:"pointer"}}>
              <rect x={stackX} y={302} width={stackW} height={26} rx={3}
                fill={purple} opacity={isSel("ECUs")?1:0.7}
                stroke={isSel("ECUs")?"#ffffff":"none"} strokeWidth={isSel("ECUs")?2:0}/>
              <text x={stackX+stackW/2} y={320} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">Embedded electronic control units</text>
              {bandInfo("ECUs",stackX,302,stackW,26)}
            </g>

            {/* ─── SEMICONDUCTORS & SENSORS ─── */}
            <g onClick={clickP("Semiconductors")} style={{cursor:"pointer"}}>
              <rect x={stackX} y={332} width={stackW} height={26} rx={3}
                fill={purple} opacity={isSel("Semiconductors")?1:0.55}
                stroke={isSel("Semiconductors")?"#ffffff":"none"} strokeWidth={isSel("Semiconductors")?2:0}/>
              <text x={stackX+stackW/2} y={350} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">Semiconductors &amp; sensors</text>
              {bandInfo("Semiconductors",stackX,332,stackW,26)}
            </g>

            {/* ─── SMART ACTUATORS ─── */}
            <g onClick={clickP("Actuators")} style={{cursor:"pointer"}}>
              <rect x={stackX} y={365} width={stackW} height={28} rx={3}
                fill={dk?"#7c3aed":"#a78bfa"} opacity={isSel("Actuators")?1:0.8}
                stroke={isSel("Actuators")?"#ffffff":"none"} strokeWidth={isSel("Actuators")?2:0}/>
              <text x={stackX+stackW/2} y={384} fill="#ffffff" fontSize="11" fontWeight="700" textAnchor="middle">Smart actuators</text>
              {bandInfo("Actuators",stackX,365,stackW,28)}
            </g>

            {/* Actuator pin decoration */}
            {Array.from({length:14}).map((_,i)=>
              <rect key={i} x={stackX+25+i*34} y={395} width={8} height={18} rx={2}
                fill={bd2} opacity={0.45}/>
            )}

            {/* ─── SIDE LABELS ─── */}
            <text x={outerX-10} y={245} fill={txt2} fontSize="9" fontWeight="700" textAnchor="middle"
              transform={`rotate(-90,${outerX-10},245)`} letterSpacing="0.06em">Processes, methods &amp; tools</text>
            <text x={outerX+outerW+18} y={350} fill={txt2} fontSize="9" fontWeight="700" textAnchor="middle"
              transform={`rotate(90,${outerX+outerW+18},350)`} letterSpacing="0.06em">Processes, methods &amp; tools</text>

            {/* NO outside icon callouts — per direction, house structure is sufficient */}

          </svg>

          {/* CAGR dot legend */}
          <div style={{display:"flex",gap:"14px",justifyContent:"center",marginTop:"4px",fontSize:"10px",color:t.c3,flexWrap:"wrap"}}>
            <span style={{fontWeight:600,color:t.c2}}>Pillar growth indicator (dot):</span>
            {[["≥15% CAGR","#22c55e","High Growth"],["5–15%","#f59e0b","Moderate"],["0–5%","#3b82f6","Stable"],["<0%","#ef4444","Declining"]].map(([l,c2,d])=>
              <span key={l} title={d} style={{display:"inline-flex",alignItems:"center",gap:"3px",cursor:"help"}}>
                <span style={{width:9,height:9,borderRadius:"50%",background:c2,display:"inline-block"}}/>{l}
              </span>
            )}
            <span style={{color:t.c3,fontStyle:"italic",marginLeft:"6px"}}>Number on right = pillar's FY25 market size in {SEGS[seg]?.s}</span>
          </div>
          </>;
        })()}
      </div>

      {/* Right: Technologies */}
      {v2Pil&&<div style={{width:"300px",flexShrink:0,overflowY:"auto",maxHeight:"640px",...card()}}>
        <div style={{fontSize:"11px",color:selP?.color,fontWeight:700,marginBottom:"3px"}}>GROWTH DRIVERS · {selP?.label}</div>
        <div style={{fontSize:"10px",color:t.c3,marginBottom:"10px"}}>Technologies · {SEGS[seg].s}</div>
        {/* Mini chart */}
        <div style={{height:"110px",background:t.btn,borderRadius:"8px",marginBottom:"10px",overflow:"hidden"}}>
          <svg width="100%" height="100%" viewBox="0 0 280 100" preserveAspectRatio="xMidYMid meet">
            {pilTechs.map((t2,i)=>{const mxS=Math.max(...pilTechs.map(x=>x.sz[seg]));const mxC=Math.max(...pilTechs.map(x=>x.cagr));
              const cx=15+(t2.sz[seg]/mxS)*245,cy=90-(t2.cagr/mxC)*75,r=Math.max(5,Math.min(15,5+(t2.sz[seg]/mxS)*10));const mc=MC[t2.mat];
              return <g key={i}><circle cx={cx} cy={cy} r={r} fill={`${mc}30`} stroke={mc} strokeWidth={1}/><text x={cx} y={cy-r-2} fill={t.c2} fontSize="6" textAnchor="middle">{t2.n.length>14?t2.n.slice(0,12)+"…":t2.n}</text></g>;})}
          </svg>
        </div>
        {pilTechs.length===0&&<div style={{padding:"12px",borderRadius:"8px",background:`${selP?.color||t.acc}06`,border:`1px dashed ${selP?.color||t.acc}30`,textAlign:"center",marginBottom:"8px"}}>
          <div style={{fontSize:"11px",color:selP?.color||t.acc,fontWeight:600,marginBottom:"4px"}}>No significant current market in {SEGS[seg].s}</div>
          <div style={{fontSize:"10px",color:t.c3,lineHeight:"1.5"}}>Emerging opportunity area. As {SEGS[seg].l} electrification and digitisation progresses, this pillar may develop niche applications. Monitor for early-mover advantage.</div>
        </div>}
        {pilTechs.map((t2,i)=>{const sz=t2.sz[seg];const proj=Math.round(sz*Math.pow(1+t2.cagr/100,6));const mc=MC[t2.mat];
          return <div key={i} style={{padding:"8px",marginBottom:"4px",borderRadius:"7px",background:t.btn,borderLeft:`3px solid ${mc}`}}>
            <div style={{display:"flex",justifyContent:"space-between",marginBottom:"2px"}}>
              <span style={{fontSize:"11px",fontWeight:600,color:t.c}}>{t2.n}</span>
              <span style={{fontSize:"9px",padding:"1px 5px",borderRadius:"3px",background:`${mc}18`,color:mc,fontWeight:600}}>{t2.mat}</span>
            </div>
            {t2.inc&&<div style={{fontSize:"8.5px",color:t.c3,marginBottom:"2px",fontStyle:"italic"}}>{t2.inc}</div>}
            <div style={{display:"flex",gap:"10px",fontSize:"10px",color:t.c2}}>
              <span>Size: <strong style={{color:t.c}}>{fmt(sz)}</strong></span>
              <span>CAGR: <strong style={{color:selP?.color}}>{t2.cagr}%</strong></span>
              <span>→ {fmt(proj)}</span>
            </div>
          </div>;})}
        {/* Pillar Overview — shown below the tech list */}
        {(()=>{
          const totalSize=pilTechs.reduce((s,tt)=>s+(tt.sz[seg]||0),0);
          const fastest=pilTechs.length?pilTechs.reduce((best,tt)=>tt.cagr>(best?.cagr||0)?tt:best):null;
          const largest=pilTechs.length?pilTechs.reduce((best,tt)=>(tt.sz[seg]||0)>(best?.sz?.[seg]||0)?tt:best):null;
          return(
            <div style={{marginTop:"8px",padding:"8px",borderRadius:"8px",background:`${selP?.color}08`,border:`1px solid ${selP?.color}18`}}>
              <div style={{fontSize:"10px",fontWeight:700,color:selP?.color,marginBottom:"4px"}}>◆ PILLAR OVERVIEW · {v2Pil}</div>
              <div style={{fontSize:"10px",color:t.c2,lineHeight:"1.5"}}>
                {selP?.label} pillar: <strong style={{color:t.c}}>{fmt(totalSize,curr)}</strong> for {SEGS[seg].s} ({pilTechs.length} technologies).
                {fastest&&<> Star performer: <strong style={{color:t.c}}>{fastest.n}</strong> at {fastest.cagr}% CAGR.</>}
                {largest&&<> Largest: <strong style={{color:t.c}}>{largest.n}</strong> at {fmt(largest.sz[seg],curr)}.</>}
              </div>
            </div>
          );
        })()}
        {/* GROWTH FACTORS — maturity breakdown per pillar */}
        {v2Pil&&(()=>{
          const pilTechsAll=TECHS.filter(tt=>tt.p===v2Pil);
          const topGrowers=[...pilTechsAll].sort((a,b)=>(b.cagr||0)-(a.cagr||0)).slice(0,3);
          const emergingTechs=pilTechsAll.filter(tt=>tt.mat==="Emerging");
          const growthTechs=pilTechsAll.filter(tt=>tt.mat==="Growth");
          const matureTechs=pilTechsAll.filter(tt=>tt.mat==="Mature");
          return(
            <div style={{marginTop:"8px",padding:"8px",borderRadius:"8px",border:`1px solid ${t.border}`,background:t.card}}>
              <div style={{fontSize:"10px",fontWeight:700,color:"#22c55e",marginBottom:"6px"}}>▲ GROWTH FACTORS · {v2Pil}</div>
              <div style={{fontSize:"10px",color:t.c2,lineHeight:"1.5",marginBottom:"6px"}}>
                {emergingTechs.length>0&&<div style={{marginBottom:"4px"}}><span style={{color:t.c,fontWeight:600}}>Emerging ({emergingTechs.length}):</span>{" "}{emergingTechs.map(tt=>tt.n).join(", ")}</div>}
                {growthTechs.length>0&&<div style={{marginBottom:"4px"}}><span style={{color:t.c,fontWeight:600}}>Growth ({growthTechs.length}):</span>{" "}{growthTechs.map(tt=>tt.n).join(", ")}</div>}
                {matureTechs.length>0&&<div style={{marginBottom:"4px"}}><span style={{color:t.c,fontWeight:600}}>Mature ({matureTechs.length}):</span>{" "}{matureTechs.map(tt=>tt.n).join(", ")}</div>}
              </div>
              {topGrowers.length>0&&<div style={{fontSize:"9px",color:t.c3}}>Fastest growing: {topGrowers.map(tt=>`${tt.n} (${tt.cagr}%)`).join(" · ")}</div>}
            </div>
          );
        })()}
      </div>}
    </div>);
  };

  /* ═══ VIEW 3: MARKET LANDSCAPE ═══ */
  const renderV3=()=>{
    const plOpts=[{k:"all",l:"All Pillars"},...PILLARS.map(p=>({k:p.id,l:p.label}))];
    const stOpts=["all","Emerging","Growth","Mature","Declining"];
    let data=segTechs;
    if(v3P!=="all")data=data.filter(d=>d.p===v3P);
    if(v3Stage!=="all")data=data.filter(d=>d.mat===v3Stage);
    if(v3Top>0)data=data.slice(0,v3Top);

    const yrs=v3Year-2025;
    const W=svgDim.w,H=svgDim.h;
    const pad={l:60,r:20,t:30,b:45};
    const iW=W-pad.l-pad.r,iH=H-pad.t-pad.b;
    const mxS=Math.max(...data.map(d=>Math.round(d.segSz*Math.pow(1+d.cagr/100,yrs))),1)*1.15;
    const mxC=Math.max(...data.map(d=>d.cagr),1)*1.15;
    const mnC=Math.min(0,...data.map(d=>d.cagr));
    const sx=v=>pad.l+(v/mxS)*iW;const sy=v=>pad.t+iH-((v-mnC)/(mxC-mnC))*iH;
    const sr=v=>Math.max(6,Math.min(32,6+(v/mxS)*26));

    let bubbles=data.map(d=>{const ps=Math.round(d.segSz*Math.pow(1+d.cagr/100,yrs));return{...d,projSz:ps,cx:sx(ps),cy:sy(d.cagr),r:sr(ps)};});
    // Repulsion: treat each bubble+label as a tall capsule. Label adds ~14px above.
    for(let pass=0;pass<40;pass++){for(let i=0;i<bubbles.length;i++){for(let j=i+1;j<bubbles.length;j++){
      const dx=bubbles[j].cx-bubbles[i].cx,dy=bubbles[j].cy-bubbles[i].cy,dist=Math.sqrt(dx*dx+dy*dy);
      // Effective radius includes label height above bubble
      const ri=bubbles[i].r+7,rj=bubbles[j].r+7,minD=ri+rj+14;
      if(dist<minD&&dist>0){const push=(minD-dist)/2*0.85,nx=dx/dist,ny=dy/dist;
        bubbles[i]={...bubbles[i],cx:bubbles[i].cx-nx*push,cy:bubbles[i].cy-ny*push};
        bubbles[j]={...bubbles[j],cx:bubbles[j].cx+nx*push,cy:bubbles[j].cy+ny*push};}
    }}}
    bubbles=bubbles.map(b=>({...b,cx:Math.max(pad.l+b.r,Math.min(W-pad.r-b.r,b.cx)),cy:Math.max(pad.t+b.r+12,Math.min(H-pad.b-b.r,b.cy))}));

    return(<div>
      <div style={{display:"flex",gap:"5px",marginBottom:"8px",flexWrap:"wrap",alignItems:"center"}}>
        <select value={v3P} onChange={e=>{setV3P(e.target.value);setV3T(null);setAiAnalysis(null);}} style={{padding:"4px 8px",borderRadius:"6px",border:`1px solid ${t.border}`,background:t.btn,color:t.c,fontSize:"11px"}}>
          {plOpts.map(o=><option key={o.k} value={o.k}>{o.l}</option>)}
        </select>
        {stOpts.map(s=><button key={s} onClick={()=>setV3Stage(s)} style={{padding:"4px 10px",borderRadius:"6px",border:`1px solid ${s===v3Stage?MC[s]||t.acc:t.border}`,background:s===v3Stage?`${MC[s]||t.acc}18`:t.btn,color:s===v3Stage?MC[s]||t.acc:t.c2,fontSize:"10px",fontWeight:600,cursor:"pointer"}}>{s==="all"?"All Stages":s}</button>)}
        <span style={{width:1,height:18,background:t.border,margin:"0 3px"}}/>
        {[0,5,10,15,20].map(n=><button key={n} onClick={()=>setV3Top(n)} style={{padding:"4px 7px",borderRadius:"5px",border:`1px solid ${v3Top===n?t.acc:t.border}`,background:v3Top===n?`${t.acc}18`:t.btn,color:v3Top===n?t.acc:t.c2,fontSize:"10px",fontWeight:600,cursor:"pointer"}}>{n===0?"All":`Top ${n}`}</button>)}
        <div style={{marginLeft:"auto",display:"flex",alignItems:"center",gap:"6px"}}>
          <span style={{fontSize:"10px",color:t.c2,fontWeight:600}}>Projection:</span>
          <input type="range" min={2025} max={2030} value={v3Year} onChange={e=>setV3Year(Number(e.target.value))} style={{width:"100px",accentColor:t.acc}}/>
          <span style={{fontSize:"13px",color:t.acc,fontWeight:700}}>{v3Year}</span>
        </div>
      </div>
      <div style={{...card({padding:"8px 12px",marginBottom:"8px"})}}>
        <div style={{display:"flex",gap:"14px",justifyContent:"center",alignItems:"center",flexWrap:"wrap"}}>
          {/* ── Maturity (bubble FILL color) ── */}
          <div style={{display:"flex",gap:"10px",alignItems:"center"}}>
            <span style={{fontSize:"10px",color:t.c2,fontWeight:700}}>FILL · MATURITY:</span>
            {Object.entries(MC).map(([k,c])=>{
              const matTip={"Emerging":"<5% penetration — high CAGR from small base","Growth":"5–40% penetration — rapid adoption","Mature":">40% penetration — established supply chain","Declining":"Being replaced — near-zero or negative CAGR"};
              return <div key={k} title={matTip[k]} style={{display:"flex",alignItems:"center",gap:"4px",cursor:"help"}}>
                <div style={{width:10,height:10,borderRadius:"50%",background:`${c}40`,border:`1px solid ${c}80`}}/>
                <span style={{fontSize:"10px",color:t.c,fontWeight:600}}>{k}</span>
              </div>;
            })}
          </div>
          <div style={{width:1,height:18,background:t.border}}/>
          {/* ── Velocity (glyph) ── */}
          <div style={{display:"flex",gap:"10px",alignItems:"center"}}>
            <span style={{fontSize:"10px",color:t.c2,fontWeight:700}}>GLYPH · CAGR:</span>
            <span title="CAGR ≥ 15% — fast growth" style={{display:"inline-flex",alignItems:"center",gap:"3px",cursor:"help"}}>
              <span style={{color:"#22c55e",fontWeight:700,fontSize:11}}>▲</span><span style={{fontSize:10,color:t.c}}>≥15%</span>
            </span>
            <span title="CAGR 5–15%" style={{display:"inline-flex",alignItems:"center",gap:"3px",cursor:"help"}}>
              <span style={{color:"#f59e0b",fontWeight:700,fontSize:11}}>→</span><span style={{fontSize:10,color:t.c}}>5–15%</span>
            </span>
            <span title="CAGR 0–5%" style={{display:"inline-flex",alignItems:"center",gap:"3px",cursor:"help"}}>
              <span style={{color:"#3b82f6",fontWeight:700,fontSize:11}}>■</span><span style={{fontSize:10,color:t.c}}>0–5%</span>
            </span>
            <span title="CAGR < 0%" style={{display:"inline-flex",alignItems:"center",gap:"3px",cursor:"help"}}>
              <span style={{color:"#ef4444",fontWeight:700,fontSize:11}}>▼</span><span style={{fontSize:10,color:t.c}}>&lt;0%</span>
            </span>
          </div>
          {/* ── Pillar (border) — only when All Pillars selected ── */}
          {v3P==="all" && <>
            <div style={{width:1,height:18,background:t.border}}/>
            <div style={{display:"flex",gap:"6px",alignItems:"center",flexWrap:"wrap"}}>
              <span style={{fontSize:"10px",color:t.c2,fontWeight:700}}>BORDER · PILLAR:</span>
              {Object.entries(PILLAR_COLORS).map(([p,c])=>
                <span key={p} title={p} style={{display:"inline-flex",alignItems:"center",gap:"3px"}}>
                  <span style={{width:8,height:8,borderRadius:"50%",display:"inline-block",background:"transparent",border:`2px solid ${c}`}}/>
                  <span style={{fontSize:9,color:t.c,fontWeight:500}}>{p}</span>
                </span>
              )}
            </div>
          </>}
          <div style={{width:1,height:18,background:t.border}}/>
          <span style={{fontSize:9.5,color:t.c3,fontStyle:"italic"}}>
            Size = projected market for {SEGS[seg].s} at {v3Year}
          </span>
        </div>
      </div>

      <div style={{display:"flex",gap:"14px",overflow:"hidden"}}>
        <div style={{flex:1,minWidth:0}}>
          <div ref={view===3?svgRef:null} style={{...card(),padding:0,overflow:"hidden",minHeight:"460px",position:"relative"}}>
            <svg width={W} height={H} style={{display:"block"}}>
              {[0,.25,.5,.75,1].map((f,i)=>{const v=mnC+f*(mxC-mnC);return<g key={i}><line x1={pad.l} y1={sy(v)} x2={W-pad.r} y2={sy(v)} stroke={t.grid} strokeDasharray="2,6"/><text x={pad.l-8} y={sy(v)+4} fill={t.c3} fontSize="9" textAnchor="end">{v.toFixed(0)}%</text></g>})}
              {[0,.25,.5,.75,1].map((f,i)=>{const v=f*mxS;return<g key={i}><line x1={sx(v)} y1={pad.t} x2={sx(v)} y2={H-pad.b} stroke={t.grid} strokeDasharray="2,6"/><text x={sx(v)} y={H-pad.b+14} fill={t.c3} fontSize="8" textAnchor="middle">{v>=1000?(v/1000).toFixed(1)+"K":v.toFixed(0)}</text></g>})}
              <text x={W/2} y={H-4} fill={t.c2} fontSize="10" textAnchor="middle" fontWeight="600">{v3Year===2025?"Market Size FY2025":"Market Size Projected "+v3Year} {curr==="EUR"?"€M":"₹Cr"} ({SEGS[seg].s}) →</text>
              <text x={10} y={H/2} fill={t.c2} fontSize="10" textAnchor="middle" fontWeight="600" transform={`rotate(-90,10,${H/2})`}>CAGR 2024–2030 (%) →</text>
              {/* Compute label positions with repulsion */}
              {(()=>{
                // Build label positions: each label is a rect {x,y,w,h} anchored above its bubble
                const labels=bubbles.map(b=>({n:b.n,x:b.cx,y:b.cy-b.r-6,w:Math.min(b.n.length,20)*5.5,h:10}));
                // Label-to-label repulsion (40 passes)
                for(let pass=0;pass<40;pass++){for(let i=0;i<labels.length;i++){for(let j=i+1;j<labels.length;j++){
                  const li=labels[i],lj=labels[j];
                  const ox=Math.abs(li.x-lj.x),oy=Math.abs(li.y-lj.y);
                  const minX=(li.w+lj.w)/2+6,minY=(li.h+lj.h)/2+2;
                  if(ox<minX&&oy<minY){
                    const pushX=(minX-ox)*0.35*(li.x<lj.x?-1:1);
                    const pushY=(minY-oy)*0.55*(li.y<lj.y?-1:1);
                    labels[i]={...labels[i],x:labels[i].x+pushX,y:labels[i].y+pushY};
                    labels[j]={...labels[j],x:labels[j].x-pushX,y:labels[j].y-pushY};
                  }
                }}}
                // Clamp labels within SVG bounds
                for(let i=0;i<labels.length;i++){
                  labels[i].x=Math.max(pad.l+labels[i].w/2,Math.min(W-pad.r-labels[i].w/2,labels[i].x));
                  labels[i].y=Math.max(pad.t+8,Math.min(H-pad.b-4,labels[i].y));
                }
                return bubbles.map((b,idx)=>{const mc=MC[b.mat];const pl=PM[b.p];const isSel=v3T?.n===b.n;const lb=labels[idx];
                // When "All Pillars" is selected, use pillar color for BORDER so leadership
                // can see which pillar each bubble belongs to. Fill stays = maturity.
                const showPillarBorder = v3P==="all";
                const strokeColor = showPillarBorder ? (pl?.color || mc) : `${mc}${dk?"90":"70"}`;
                const strokeWidth = isSel ? 3 : (showPillarBorder ? 2 : 1);
                return <g key={b.n} style={{cursor:"pointer"}} onClick={()=>{if(isSel){setV3T(null);setAiAnalysis(null);}else{setV3T(b);if(b._code)fetchTechAnalysis(b._code);}}}>
                  <title>{b.n} — {fmt(b.segSz,curr)} · CAGR: {b.cagr}% · {b.mat} · {b.p}</title>
                  {isSel&&<circle cx={b.cx} cy={b.cy} r={b.r+5} fill="none" stroke={pl?.color} strokeWidth={2.5} opacity={0.5}/>}
                  <circle cx={b.cx} cy={b.cy} r={b.r} fill={`${mc}${dk?"28":"18"}`} stroke={strokeColor} strokeWidth={strokeWidth}/>
                  {(()=>{
                    // Velocity glyph: ▲ if CAGR > 15, → if 5-15, ■ flat 0-5, ▼ if declining
                    const gx = b.cx + b.r*0.55;
                    const gy = b.cy - b.r*0.55;
                    const glyph = b.cagr >= 15 ? "▲" : b.cagr >= 5 ? "→" : b.cagr < 0 ? "▼" : "■";
                    const gColor = b.cagr >= 15 ? "#22c55e" : b.cagr >= 5 ? "#f59e0b" : b.cagr < 0 ? "#ef4444" : "#3b82f6";
                    return <>
                      <circle cx={gx} cy={gy} r={6} fill={dk?"#0a0e1a":"#ffffff"} stroke={gColor} strokeWidth={1}/>
                      <text x={gx} y={gy+3} fontSize="7" textAnchor="middle" fill={gColor} fontWeight="700">{glyph}</text>
                    </>;
                  })()}
                  <line x1={b.cx} y1={b.cy-b.r} x2={lb.x} y2={lb.y+4} stroke={t.c3} strokeWidth={0.4} opacity={0.3}/>
                  <text x={lb.x} y={lb.y} fill={t.c} fontSize="8" fontWeight="600" textAnchor="middle" opacity={0.85}>{b.n.length>20?b.n.slice(0,18)+"…":b.n}</text>
                </g>;});
              })()}
            </svg>
          </div>
          <div style={{marginTop:"10px",fontSize:"11px",color:t.c3,fontWeight:600,marginBottom:"4px"}}>RANKED BY SIZE {v3Year>2025?`(${v3Year})`:""} · {v3P==="all"?"All":PM[v3P]?.label} · {SEGS[seg].s}</div>
          <div style={{display:"flex",flexDirection:"column",gap:"2px"}}>
            {bubbles.slice(0,15).map((d,i)=>{const pl=PM[d.p];const mx=bubbles[0]?.projSz||1;
              return <div key={i} onClick={()=>{setV3T(d);setAiAnalysis(null);if(d._code)fetchTechAnalysis(d._code);}} style={{display:"flex",alignItems:"center",gap:"6px",padding:"4px 6px",borderRadius:"5px",cursor:"pointer",background:v3T?.n===d.n?`${pl?.color}08`:undefined,border:v3T?.n===d.n?`1px solid ${pl?.color}25`:"1px solid transparent"}}>
                <span style={{fontSize:"10px",color:t.c3,minWidth:"16px",textAlign:"center"}}>{i+1}</span>
                <div style={{width:3,height:18,borderRadius:1,background:pl?.color}}/>
                <div style={{flex:1,minWidth:0}}><div style={{fontSize:"11px",fontWeight:600,color:t.c,whiteSpace:"nowrap",overflow:"hidden",textOverflow:"ellipsis"}}>{d.n}</div><div style={{fontSize:"8px",color:pl?.color}}>{pl?.label} · <span style={{color:MC[d.mat]}}>{d.mat}</span></div></div>
                <div style={{flex:1.5,height:5,background:t.bar,borderRadius:2,overflow:"hidden"}}><div style={{height:"100%",borderRadius:2,background:`linear-gradient(90deg,${pl?.color}50,${pl?.color})`,width:`${(d.projSz/mx)*100}%`}}/></div>
                <span style={{fontSize:"10px",fontWeight:700,color:t.acc,minWidth:"38px",textAlign:"right"}}>{d.cagr}%</span>
                <span style={{fontSize:"9px",color:t.c2,minWidth:"50px",textAlign:"right"}}>{fmt(d.projSz)}</span>
              </div>;})}
          </div>
        </div>

        {v3T&&(()=>{const d=v3T;const pl=PM[d.p];
          const years=[2025,2026,2027,2028,2029,2030];
          const proj=years.map(y=>({y,sz:Math.round(d.segSz*Math.pow(1+d.cagr/100,y-2025))}));
          const mx=Math.max(...proj.map(p=>p.sz));
          const pilForces=PESTEL.filter(f=>f.pil.includes(d.p)&&isPestelRelevantForSegment(f,seg)).sort((a,b)=>(b.rel[seg]==="H"?1:0)-(a.rel[seg]==="H"?1:0));
          const segCtx={"4W_PV":"premiumization, SUV dominance, and record 43L dispatches","LCV":"last-mile delivery boom and fleet digitization","HCV":"BS-VI/AEBS compliance and scrappage replacement","2W":"EV price war (7.4% penetration) and OBD-II mandate","3W":"EV dominance (>50%) and BaaS adoption","Tractor":"TREM V compliance and precision agriculture"}[seg]||"";
          // Pillar-level overview data
          const pilTotalSz=TECHS.filter(tt=>tt.p===d.p).reduce((s,tt)=>s+(tt.sz[seg]||0),0);
          const pilTechs2=TECHS.filter(tt=>tt.p===d.p&&tt.sz[seg]>0).sort((a,b)=>b.cagr-a.cagr);
          const topGrower=pilTechs2[0];const maxSzTech=TECHS.filter(tt=>tt.p===d.p&&tt.sz[seg]>0).sort((a,b)=>b.sz[seg]-a.sz[seg])[0];
          // Tech-specific, segment-aware growth drivers and risks
          const mkDrivers=(tech,sg)=>{
            const s=SEGS[sg]?.s||"";const sl=SEGS[sg]?.l||"";const D=[];const R=[];
            // Universal drivers/risks based on maturity
            if(tech.mat==="Emerging"){D.push(`First-mover advantage in ${s} — <5% penetration today`);R.push(`Unproven demand at scale for ${s} segment`);}
            if(tech.mat==="Growth"){D.push(`Proven demand scaling — ${tech.cagr}% CAGR for ${s}`);R.push(`Competitive intensity rising — margin pressure`);}
            if(tech.mat==="Mature"){D.push(`Established revenue base — steady ${tech.cagr}% for ${s}`);R.push(`Growth ceiling — innovation needed to avoid commoditization`);}
            if(tech.mat==="Declining"){D.push(`Aftermarket servicing creates residual revenue`);R.push(`Technology obsolescence — pivot to replacement tech required`);}
            // Segment-specific drivers
            if(sg==="4W_PV"){D.push("SUV premiumization (66% of PV) driving content per vehicle");if(tech.cagr>15)D.push("Record 43L dispatches FY25 amplifying high-growth adoption");D.push("Electronics content per SUV 2-3x vs. hatchback — ₹35K to ₹1.2L");}
            if(sg==="2W"){D.push("OBD-II mandate (Apr 2025) tripling electronics content per 2W");D.push("E-2W price war — Ola S1 Air ₹69,999 cheaper than ICE");}
            if(sg==="3W"){D.push("E-3W >50% in metros — fastest EV transition globally");D.push("BaaS reducing upfront cost 40%, enabling 24/7 operation");}
            if(sg==="HCV"){D.push("AEBS/DDAWS mandate Apr 2026 for >8 pax vehicles");D.push("Scrappage policy — 11L+ old trucks creating replacement demand");}
            if(sg==="LCV"){D.push("Last-mile e-commerce boom driving LCV fleet digitization");D.push("Amazon/Flipkart mandating telematics in delivery fleets");}
            if(sg==="Tractor"){D.push("TREM V emission norms (2026) — biggest regulatory change in decade");D.push("Precision agriculture — GPS auto-steering saving 15% fuel");}
            // Tech-specific drivers
            const tn=tech.n.toLowerCase();
            if(tn.includes("aeb")||tn.includes("emergency"))D.push("Bharat NCAP requiring AEB for 5-star (BNCAP 2.0 from 2027)");
            if(tn.includes("battery")&&tn.includes("pack"))D.push("Battery cost declining to $100/kWh by 2028 — parity enabler");
            if(tn.includes("infotainment"))D.push("10\"+ touchscreens standard even in ₹6L cars — non-negotiable feature");
            if(tn.includes("wiring"))D.push("Complexity growing 15% per model generation with electronics content");
            if(tn.includes("interior"))D.push("Premium interiors command ₹50-80K price premium per vehicle");
            if(tn.includes("seat")||tn.includes("restraint"))D.push("6-airbag mandatory from Oct 2025 — ₹8-12K per vehicle increase");
            if(tn.includes("lighting")||tn.includes("adaptive"))D.push("LED standard — matrix beam and DRL as competitive differentiator");
            if(tn.includes("ota"))D.push("Feature-on-demand via OTA creating recurring SaaS-like revenue");
            if(tn.includes("sic"))D.push("800V architecture adoption — 30% range improvement for EVs");
            if(tn.includes("radar"))D.push("77GHz radar becoming standard for L2+ vehicles under ₹20L");
            if(tn.includes("charging"))D.push("29K+ public stations by Aug 2025, growing 40%+ annually");
            if(tn.includes("fleet"))D.push("AIS-140 GPS mandate enforced in 12+ states for public transport");
            if(tn.includes("dms")||tn.includes("driver monitor"))D.push("MoRTH fatigue detection mandate for commercial vehicles");
            if(tn.includes("eps")||tn.includes("steering"))D.push("EPS penetration rising from 45% to 80% in PV by 2030");
            if(tn.includes("exhaust")||tn.includes("emission"))D.push("BS-VI Stage 2 RDE norms increasing aftertreatment complexity");
            if(tn.includes("thermal")||tn.includes("hvac"))D.push("EV battery thermal management becoming critical differentiator");
            if(tn.includes("bms")||tn.includes("battery mgmt"))D.push("Cell-level monitoring becoming insurance and warranty requirement");
            if(tn.includes("body panel"))D.push("Multi-material BIW (aluminum + steel) for lightweighting");
            if(tn.includes("chassis"))D.push("Unibody platforms replacing ladder frame in PV — material shift");
            if(tn.includes("powertrain")&&tn.includes("engine"))D.push("Turbo/GDI adoption rising — higher precision component demand");
            if(tn.includes("xev powertrain")||tn.includes("e-axle"))D.push("Motor + inverter + gearbox integration reducing cost 20-30%");
            if(tn.includes("ecu")&&tn.includes("generic"))D.push("Aftermarket replacement ECU demand remains strong");
            if(tn.includes("autosar"))D.push("SDV architecture transition driving demand for new OS frameworks");
            if(tn.includes("compute")||tn.includes("zone"))D.push("Zonal architecture replacing 70+ distributed ECUs per vehicle");
            // Tech-specific risks
            if(tn.includes("xev")||tn.includes("e-axle")||tn.includes("e-motor"))R.push("Rare earth magnet supply — 80% from China, $788M incentive helps");
            if(tn.includes("infotainment"))R.push("AAOS (Android Automotive) reducing Tier-1 software differentiation");
            if(tn.includes("safety"))R.push("Liability framework for electronic safety system failures unclear");
            if(tn.includes("semiconductor")||tn.includes("sic"))R.push("Fab capex very high — ₹76K Cr for single facility");
            if(tn.includes("ota")||tn.includes("cloud")||tn.includes("v2x"))R.push("AIS-189 cybersecurity compliance adding ₹5-8K per vehicle");
            if(tn.includes("battery"))R.push("Raw material volatility — lithium, cobalt price swings");
            if(tn.includes("charging"))R.push("Charging business model profitability still unproven");
            if(tn.includes("body")||tn.includes("chassis")||tn.includes("wheel"))R.push("EU CBAM carbon tax on steel/aluminum exports from 2026");
            if(tn.includes("engine")||tn.includes("fuel")||tn.includes("exhaust"))R.push("Long-term ICE decline as EV share grows — stranded asset risk");
            if(tn.includes("wiring"))R.push("Copper price volatility and shift to aluminum harness");
            if(tn.includes("radar")||tn.includes("camera")||tn.includes("sensor"))R.push("Red Sea disruption — 4-8 week semiconductor lead time increase");
            if(tn.includes("fleet")||tn.includes("logistics"))R.push("Competition from IT companies (TCS, Infosys) entering fleet SW");
            if(tn.includes("autosar")||tn.includes("linux")||tn.includes("os"))R.push("Talent shortage for embedded automotive OS development in India");
            if(tn.includes("ecu"))R.push("Centralization trend reducing total ECU count per vehicle");
            if(tn.includes("compute")||tn.includes("zone")||tn.includes("domain"))R.push("High SoC cost and thermal management challenges");
            if(tn.includes("interior")||tn.includes("seat"))R.push("Material cost inflation from premiumization requirements");
            // Geopolitical risk for all
            if(tech.cagr>20)R.push(`High-growth (${tech.cagr}%) attracts competition — differentiation critical`);
            R.push("Geopolitical/Red Sea disruption affecting component supply chains");
            return{drivers:D.slice(0,4),risks:R.slice(0,4)};
          };
          const{drivers,risks}=mkDrivers(d,seg);
          const players={"ADAS":"Bosch, Continental, Valeo, Mobileye, KPIT, Tata Elxsi","Motion":"Bosch, ZF, BorgWarner, Dana, Sona Comstar, Tata AutoComp","Energy":"Exide Energy, Amara Raja, Tata AutoComp, Bosch, BorgWarner","Body & Comfort":"Motherson, Minda, Valeo, Samvardhana, JBM Auto, Lumax","Infotainment":"Bosch, Continental, Visteon, KPIT, Tata Elxsi, Harman","Solutions":"Bosch Connected, BlackBuck, Rivigo, Tata Technologies","Services":"MapmyIndia, Bosch, Continental, TomTom, HERE","Cloud":"Bosch IoT, AWS IoT, Azure, Tata Communications","OS":"Bosch, ETAS, Vector, Elektrobit, KPIT","Compute":"Bosch, Continental, Aptiv, NVIDIA (via Tier-1s)","ECUs":"Bosch, Continental, Denso, Keihin, Minda","Semiconductors":"STMicro, Infineon, NXP, RIR Power, Tata Electronics","Actuators":"Bosch, Continental, Mando (Halla), Brembo, Sona BLW"}[d.p]||"";
          return <div style={{width:"360px",flexShrink:0,overflowY:"auto",maxHeight:"700px",...card()}}>
            <div style={{display:"flex",alignItems:"center",gap:"5px",marginBottom:"5px"}}>
              <div style={{width:7,height:7,borderRadius:"50%",background:pl?.color}}/><span style={{fontSize:"10px",color:pl?.color,fontWeight:700}}>AI AGENT ANALYSIS · {SEGS[seg].s}</span>
            </div>
            <h3 style={{margin:"0 0 4px",fontSize:"15px",fontWeight:700,color:t.c}}>{d.n}</h3>
            {d.inc&&<div style={{fontSize:"9px",color:t.c3,marginBottom:"6px",fontStyle:"italic"}}>Includes: {d.inc}</div>}
            <div style={{display:"flex",gap:"4px",marginBottom:"8px",flexWrap:"wrap"}}>
              <span style={{fontSize:"9px",padding:"2px 7px",borderRadius:"4px",background:`${pl?.color}15`,color:pl?.color,fontWeight:600,border:`1px solid ${pl?.color}25`}}>Stack: {pl?.label}</span>
              <span style={{fontSize:"9px",padding:"2px 7px",borderRadius:"4px",background:`${MC[d.mat]}15`,color:MC[d.mat],fontWeight:600}}>{d.mat}</span>
              {(()=>{const sn=d.source_note||d.src||"";const snL=sn.toLowerCase();const isP=snL.startsWith("published:");const isD=snL.startsWith("derived from");const bg=isP?"#22c55e15":isD?"#f9731615":"#ef444415";const clr=isP?"#22c55e":isD?"#f97316":"#ef4444";const lbl=isP?sn.replace(/^Published:\s*/i,"").split(" Report")[0].split(",")[0].split(" India")[0]:isD?"Derived \u00b7 "+sn.replace(/^Derived from\s*/i,"").split(" ").slice(0,3).join(" "):sn&&sn.length<60&&sn!=="API"&&sn!=="Live API"?sn:"AI Estimate";return(<span style={{fontSize:"9px",padding:"2px 5px",borderRadius:"3px",background:bg,color:clr,fontWeight:600}}>{lbl}</span>);})()}
            </div>
            <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr",gap:"4px",marginBottom:"8px"}}>
              {/* FY2025 — shows data confidence badge */}
              <div style={{padding:"5px",background:t.btn,borderRadius:"6px",textAlign:"center"}}>
                <div style={{fontSize:"8px",color:t.c3}}>FY2025</div>
                <div style={{fontSize:"14px",fontWeight:700,color:t.c}}>{fmt(d.segSz)}</div>
                {(()=>{const sn=d.source_note||d.src||"";const snL=sn.toLowerCase();const isP=snL.startsWith("published:");const isD=snL.startsWith("derived from");return(
                  <div style={{fontSize:"8px",marginTop:"2px",padding:"1px 5px",borderRadius:"3px",display:"inline-block",
                    background:isP?"#22c55e15":isD?"#f9731615":"#ef444415",color:isP?"#22c55e":isD?"#f97316":"#ef4444",border:`1px solid ${isP?"#22c55e30":isD?"#f9731630":"#ef444430"}`}}>
                    {isP?sn.replace(/^Published:\s*/i,"").split(" Report")[0].split(",")[0].split(" India")[0]:isD?"Derived \u00b7 "+sn.replace(/^Derived from\s*/i,"").split(" ").slice(0,3).join(" "):sn&&sn.length<60&&sn!=="API"?sn:"AI Estimate"}
                  </div>
                );})()}
                {(()=>{const sn=d.source_note||d.src||"";const snL=sn.toLowerCase();const isNamed=snL.startsWith("published:")||snL.startsWith("derived from")||snL.includes("acma")||snL.includes("siam")||snL.includes("mordor")||snL.includes("imarc")||snL.includes("ibef")||snL.includes("crisil")||snL.includes("frost");if(!isNamed){const basis=sn&&sn.length<100&&sn!=="API"&&sn!=="Live API"?sn:"Proportional sizing from segment volume \u00d7 adoption rates";return <div style={{fontSize:"7px",color:t.c3,marginTop:"1px",fontStyle:"italic",maxWidth:"120px",textAlign:"center",lineHeight:"1.3"}}>Basis: {basis}</div>;}return null;})()}
              </div>
              {/* CAGR — uses pillar colour */}
              <div style={{padding:"5px",background:t.btn,borderRadius:"6px",textAlign:"center"}}>
                <div style={{fontSize:"8px",color:t.c3}}>CAGR</div>
                <div style={{fontSize:"14px",fontWeight:700,color:pl?.color}}>{`${d.cagr}%`}</div>
              </div>
              {/* FY2030 — always projected math */}
              <div style={{padding:"5px",background:t.btn,borderRadius:"6px",textAlign:"center"}}>
                <div style={{fontSize:"8px",color:t.c3}}>FY2030</div>
                <div style={{fontSize:"14px",fontWeight:700,color:t.c}}>{fmt(proj[5].sz)}</div>
                <div style={{fontSize:"8px",marginTop:"2px",padding:"1px 5px",borderRadius:"3px",display:"inline-block",
                  background:"#3b82f615",color:"#3b82f6",border:"1px solid #3b82f630"}}>
                  FY25×(1+CAGR)⁵
                </div>
              </div>
            </div>

            {/* Strategic Insight */}
            <div style={{padding:"8px",borderRadius:"8px",background:`${pl?.color}06`,border:`1px solid ${pl?.color}12`,marginBottom:"6px"}}>
              <div style={{fontSize:"10px",color:pl?.color,fontWeight:700,marginBottom:"3px"}}>◆ STRATEGIC OUTLOOK · {SEGS[seg].s.toUpperCase()}</div>
              <div style={{fontSize:"10.5px",color:t.c2,lineHeight:1.55}}>
                {d.n} for {SEGS[seg].l}: {fmt(d.segSz)} → {fmt(proj[5].sz)} driven by {segCtx}.
                {d.mat==="Emerging"?` First-mover opportunity (<5% penetration). ${(proj[5].sz/d.segSz).toFixed(1)}x growth potential. Early investment = defensible market position.`
                :d.mat==="Growth"?` Proven demand scaling rapidly. Competitive intensity rising — differentiation via quality/localization critical. Window for market entry narrowing.`
                :d.mat==="Mature"?` Established market — margin optimization and share defense. Innovation through adjacent tech (connected, lightweight) creates differentiation.`
                :` Declining — monitor transition timeline. Pivot R&D investment to replacement technologies. Extract remaining value through aftermarket.`}
              </div>
            </div>

            {/* Growth Trajectory */}
            <div style={{fontSize:"10px",color:t.c3,fontWeight:600,marginBottom:"3px"}}>GROWTH TRAJECTORY 2025→2030</div>
            <div style={{display:"flex",flexDirection:"column",gap:"2px",marginBottom:"6px"}}>
              {proj.map(p=><div key={p.y} style={{display:"flex",alignItems:"center",gap:"4px"}}>
                <span style={{fontSize:"10px",color:p.y===v3Year?t.acc:t.c2,fontWeight:p.y===v3Year?700:400,minWidth:"28px"}}>{p.y}</span>
                <div style={{flex:1,height:p.y===v3Year?8:4,background:t.bar,borderRadius:3,overflow:"hidden",transition:"all .3s"}}><div style={{height:"100%",borderRadius:3,background:p.y===v3Year?pl?.color:`${pl?.color}50`,width:`${(p.sz/mx)*100}%`,transition:"all .3s"}}/></div>
                <span style={{fontSize:"10px",color:p.y===v3Year?t.c:t.c2,fontWeight:p.y===v3Year?700:400,minWidth:"50px",textAlign:"right"}}>{fmt(p.sz)}</span>
              </div>)}
            </div>

            {/* PESTEL Forces */}
            {pilForces.length>0&&<div style={{marginBottom:"6px"}}>
              <div style={{fontSize:"10px",color:t.c3,fontWeight:600,marginBottom:"3px"}}>PESTEL FORCES · {SEGS[seg].s}</div>
              {pilForces.slice(0,4).map(f=>{const cc=CAT[f.cat].c;return <div key={f.id} style={{padding:"4px 6px",marginBottom:"2px",borderRadius:"5px",background:`${cc}08`,borderLeft:`2px solid ${cc}50`,fontSize:"10px"}}>
                <div style={{display:"flex",justifyContent:"space-between",alignItems:"center"}}><span style={{fontWeight:600,color:t.c}}>{f.name.length>24?f.name.slice(0,22)+"…":f.name}</span><div style={{display:"flex",gap:"3px"}}><span style={{fontSize:"8px",padding:"1px 4px",borderRadius:"2px",background:`${cc}15`,color:cc,fontWeight:600}}>{CAT[f.cat].l.charAt(0)}</span><span style={{color:f.rel[seg]==="H"?"#ef4444":"#eab308",fontWeight:600,fontSize:"9px"}}>{f.rel[seg]}</span></div></div>
              </div>;})}
            </div>}

            {/* Cross Segments */}
            <div style={{fontSize:"10px",color:t.c3,fontWeight:600,marginBottom:"2px"}}>ACROSS SEGMENTS</div>
            {Object.entries(d.sz).filter(([_,v])=>v>0).map(([s,v])=>{const mx2=Math.max(...Object.values(d.sz).filter(x=>x>0));
              return <div key={s} style={{display:"flex",alignItems:"center",gap:"3px",padding:"1px 0",opacity:s===seg?1:0.3}}>
                <span style={{fontSize:"9px",minWidth:"48px",color:s===seg?t.c:t.c2}}>{SEGS[s]?.ic} {SEGS[s]?.s}</span>
                <div style={{flex:1,height:3,background:t.bar,borderRadius:2,overflow:"hidden"}}><div style={{height:"100%",borderRadius:2,background:s===seg?pl?.color:`${t.c3}50`,width:`${(v/mx2)*100}%`}}/></div>
                <span style={{fontSize:"8px",color:s===seg?t.c:t.c3,minWidth:"42px",textAlign:"right"}}>{fmt(v)}</span>
              </div>;})}
            <div style={{fontSize:"8px",color:t.c3,marginTop:"4px"}}>Src: {d.src}</div>
            {/* Data confidence indicator — reads source_note directly; no heuristic fallbacks */}
            {(()=>{const sn=d.source_note||d.src||"";const snL=sn.toLowerCase();const isP=snL.startsWith("published:");const isD=snL.startsWith("derived from");const bg=isP?"#22c55e08":isD?"#f9731608":"#ef444408";const border=isP?"#22c55e20":isD?"#f9731620":"#ef444420";const clr=isP?"#22c55e":isD?"#f97316":"#ef4444";const label=isP?"\u2705 DATA CONFIDENCE: HIGH":isD?"\uD83D\uDD36 DATA CONFIDENCE: MEDIUM":"\u26A0\uFE0F DATA CONFIDENCE: LOW";const srcName=isP?sn.replace(/^Published:\s*/i,"").split(" Report")[0].split(",")[0]:isD?sn.replace(/^Derived from\s*/i,"").split(" ").slice(0,4).join(" "):"AI estimate";const note=isP?`Market size and CAGR from ${srcName}. FY2030 projection: FY25 \u00d7 (1+CAGR)\u2075.`:isD?`Market size derived from ${srcName} using industry sizing. Directional estimate.`:`Market size is an AI-generated estimate. Directional only \u2014 verify before strategic decisions.`;return(<div style={{padding:"6px 8px",borderRadius:"6px",marginTop:"6px",background:bg,border:`1px solid ${border}`}}><div style={{fontSize:"9px",fontWeight:600,color:clr}}>{label}</div><div style={{fontSize:"8px",color:t.c3,marginTop:"2px"}}>{note}</div></div>);})()}
            {aiLoading&&<div style={{padding:"12px",textAlign:"center",color:t.c3,fontSize:"11px"}}>⏳ Generating AI analysis via Claude Sonnet 4.6...</div>}
            {aiAnalysis&&!aiLoading&&<div style={{marginTop:"10px",padding:"12px",borderRadius:"8px",
              border:`1px solid ${t.border}`,background:`${pl?.color}05`}}>
              {/* Strategic Outlook */}
              {(aiAnalysis.strategic_outlook||aiAnalysis.summary)&&(
                <div style={{fontSize:"11px",color:t.c,lineHeight:"1.6",marginBottom:"10px"}}>
                  {aiAnalysis.strategic_outlook||aiAnalysis.summary}
                </div>
              )}
              {/* Growth Drivers */}
              {aiAnalysis.growth_drivers&&aiAnalysis.growth_drivers.length>0&&(
                <div style={{marginBottom:"10px"}}>
                  <div style={{fontSize:"9px",fontWeight:700,color:"#22c55e",marginBottom:"4px",letterSpacing:"0.04em"}}>▲ GROWTH DRIVERS</div>
                  {aiAnalysis.growth_drivers.map((g,i)=>(
                    <div key={i} style={{fontSize:"10px",color:t.c2,padding:"3px 8px",borderLeft:`2px solid #22c55e50`,marginBottom:"3px",lineHeight:"1.45"}}>{g}</div>
                  ))}
                </div>
              )}
              {/* Key Dates */}
              {aiAnalysis.key_dates&&(()=>{const kd=aiAnalysis.key_dates;const chips=Object.entries(kd).filter(([,v])=>v&&v.length>0);return chips.length>0?(
                <div style={{display:"flex",flexWrap:"wrap",gap:"4px",marginBottom:"10px"}}>
                  {chips.map(([k,v])=>(
                    <span key={k} style={{fontSize:"9px",padding:"2px 7px",borderRadius:"10px",background:`${pl?.color}20`,color:pl?.color,fontWeight:600}}>
                      {k.replace(/_/g," ")}: {v}
                    </span>
                  ))}
                </div>
              ):null;})()}
              {/* Financial Context */}
              {aiAnalysis.financial_context&&(()=>{const fc=aiAnalysis.financial_context;const rows=Object.entries(fc).filter(([,v])=>v&&v!=="N/A");return rows.length>0?(
                <div style={{marginBottom:"10px",padding:"8px",borderRadius:"6px",background:`${pl?.color}0a`,border:`1px solid ${pl?.color}20`}}>
                  <div style={{fontSize:"9px",fontWeight:700,color:pl?.color,marginBottom:"5px",letterSpacing:"0.05em"}}>◆ FINANCIAL CONTEXT</div>
                  {rows.map(([k,v])=>(
                    <div key={k} style={{display:"flex",justifyContent:"space-between",fontSize:"10px",marginBottom:"2px"}}>
                      <span style={{color:t.c3,textTransform:"capitalize"}}>{k.replace(/_/g," ")}</span>
                      <span style={{color:t.c,fontWeight:600,maxWidth:"55%",textAlign:"right"}}>{v}</span>
                    </div>
                  ))}
                </div>
              ):null;})()}
              {/* Citations */}
              {aiAnalysis.citations&&aiAnalysis.citations.length>0&&(
                <div style={{marginBottom:"8px"}}>
                  <div style={{fontSize:"9px",fontWeight:700,color:t.c3,marginBottom:"3px",letterSpacing:"0.04em"}}>CITATIONS</div>
                  {aiAnalysis.citations.slice(0,2).map((c2,i)=>(
                    <div key={i} style={{fontSize:"9px",color:t.c3,lineHeight:"1.4",marginBottom:"2px"}}>
                      <span style={{fontWeight:600,color:t.c2}}>[{i+1}]</span> {typeof c2==="object"?`${c2.claim} — ${c2.source}`:c2}
                    </div>
                  ))}
                </div>
              )}
              {/* Model attribution */}
              <div style={{fontSize:"9px",color:t.c3,borderTop:`1px solid ${t.border}`,paddingTop:"6px",marginTop:"4px"}}>
                {aiAnalysis._meta?.model||"claude-sonnet-4-6"}{aiAnalysis._meta?.generated_at&&` · ${new Date(aiAnalysis._meta.generated_at).toLocaleString()}`}{aiAnalysis._from_cache&&" · ⚡ cached"}
              </div>
              {/* ── V3→V4 cross-link: drill into competitor landscape ── */}
              {v3T && <div style={{marginTop:"10px",borderTop:`1px solid ${t.border}`,paddingTop:"10px"}}>
                <div style={{fontSize:"9px",color:t.c3,fontWeight:700,marginBottom:"4px",letterSpacing:"0.04em"}}>
                  ↓ DEEPER ANALYSIS
                </div>
                <button
                  onClick={()=>{
                    setV4Pillar(v3T.p);
                    setV4DrillTech(v3T._code || v3T.n);
                    setV4Mode("drilldown");
                    setView(4);
                  }}
                  style={{
                    width:"100%",padding:"10px 12px",borderRadius:"8px",
                    border:`1px solid ${t.acc}50`,background:`${t.acc}10`,
                    color:t.acc,fontSize:"11px",fontWeight:700,cursor:"pointer",
                    display:"flex",alignItems:"center",justifyContent:"space-between",
                  }}
                  onMouseEnter={e=>e.currentTarget.style.background=`${t.acc}1c`}
                  onMouseLeave={e=>e.currentTarget.style.background=`${t.acc}10`}>
                  <span>◉ View competitive landscape for {v3T.n}</span>
                  <span style={{fontSize:"14px"}}>→</span>
                </button>
                <div style={{fontSize:"9px",color:t.c3,marginTop:"4px",fontStyle:"italic",textAlign:"center"}}>
                  Who supplies this in {SEGS[seg]?.s}? · OEM sourcing · Bosch position
                </div>
              </div>}
            </div>}
          </div>;})()}
      </div>
    </div>);
  };

  /* ═══ VIEW 4: COMPETITOR LANDSCAPE ═══ */
  const renderV4=()=>{
    const allPillars=["ADAS","Motion","Energy","Body & Comfort","Infotainment","Semiconductors","Actuators","OS","Compute","ECUs","Solutions","Services","Cloud"];
    const pillarColors={"ADAS":"#185FA5","Motion":"#1D9E75","Energy":"#639922","Body & Comfort":"#BA7517","Infotainment":"#D85A30","Semiconductors":"#534AB7","Actuators":"#993556","OS":"#0F6E56","Compute":"#854F0B","ECUs":"#A32D2D","Solutions":"#3C3489","Services":"#5F5E5A","Cloud":"#185FA5"};
    const pc=pillarColors[v4Pillar]||"#185FA5";
    const d=v4Data;
    const players=d?.players||[];
    // V4 API returns flat fields (fy25, cagr, maturity) — NOT market_data.
    // Build a synthetic sz object from the flat fy25 field so
    // isTechRelevantForSegment's `tech.sz?.[segment]` check works.
    const _allTechs = d?.technologies || [];
    const techs = _allTechs.filter(t => {
      const fy25Num = parseFloat(t.fy25) || 0;
      // Synthetic sz dict — only the current segment is needed
      const synthSz = { [seg]: fy25Num };
      return isTechRelevantForSegment({n: t.name, p: v4Pillar, sz: synthSz}, seg, 1);
    });
    const td=v4TechData;
    // Use the parent-scope fmt so INR/EUR toggle actually works in this view.
    const fmtFy30=(fy25,cagr)=>fmt(Math.round((fy25||0)*Math.pow(1+(cagr||0)/100,5)));
    const barColors=["#185FA5","#1D9E75","#639922","#BA7517","#D85A30","#534AB7","#993556","#0F6E56","#854F0B","#A32D2D","#888780","#B4B2A9"];

    if(v4Loading)return(<div style={{textAlign:"center",padding:60,color:t.c3}}><div style={{fontSize:24,marginBottom:8}}>&#9203;</div>Loading competitor data...</div>);

    if(!d||players.length===0)return(<div style={{textAlign:"center",padding:60,color:t.c3}}>
      <div style={{fontSize:32,marginBottom:8}}>&#128202;</div>
      <div style={{fontWeight:500,marginBottom:4}}>No competitor data for {v4Pillar} &middot; {SEGS[seg]?.s}</div>
      <div style={{fontSize:12}}>Run seed_competitors.py or select a different pillar/segment</div></div>);

    return(<div>
      {/* Pillar pills */}
      <div style={{display:"flex",gap:"5px",marginBottom:"12px",flexWrap:"wrap"}}>
        {allPillars.map(p=>(
          <button key={p} onClick={()=>{setV4Pillar(p);setV4Mode("overview");setV4DrillTech(null);}}
            style={{padding:"4px 10px",borderRadius:"6px",fontSize:"11px",fontWeight:600,cursor:"pointer",
              border:`1.5px solid ${v4Pillar===p?pc:t.border}`,
              background:v4Pillar===p?`${pc}15`:"transparent",
              color:v4Pillar===p?pc:t.c2}}>{p}</button>
        ))}
      </div>

      {/* Mode toggle */}
      <div style={{display:"flex",gap:"6px",marginBottom:"12px",alignItems:"center"}}>
        <button onClick={()=>{setV4Mode("overview");setV4DrillTech(null);}}
          style={{padding:"6px 14px",borderRadius:"6px",fontSize:"11px",fontWeight:600,cursor:"pointer",
            border:`1.5px solid ${v4Mode==="overview"?pc:t.border}`,
            background:v4Mode==="overview"?pc:"transparent",
            color:v4Mode==="overview"?"#fff":t.c2}}>Pillar Overview</button>
        <button onClick={()=>setV4Mode("drilldown")}
          style={{padding:"6px 14px",borderRadius:"6px",fontSize:"11px",fontWeight:600,cursor:"pointer",
            border:`1.5px solid ${v4Mode==="drilldown"?pc:t.border}`,
            background:v4Mode==="drilldown"?pc:"transparent",
            color:v4Mode==="drilldown"?"#fff":t.c2}}>Technology Drill-down</button>
        <div style={{marginLeft:"auto",fontSize:"10px",color:t.c3,fontStyle:"italic"}}>
          &#9888;&#65039; AI Estimate &mdash; All shares are indicative, not published
        </div>
      </div>

      {/* Breadcrumb for drill-down */}
      {v4Mode==="drilldown"&&<div style={{fontSize:"11px",color:t.c3,marginBottom:"10px",display:"flex",alignItems:"center",gap:"6px"}}>
        <span style={{cursor:"pointer",color:t.acc}} onClick={()=>{setV4Mode("overview");setV4DrillTech(null);}}>{v4Pillar} pillar</span>
        <span style={{margin:"0 2px"}}>&rarr;</span>
        <span style={{fontWeight:600,color:t.c}}>{td?.tech_name||"Select a technology"}</span>
        <span style={{flex:1}}/>
        {/* Back to V3 link */}
        <button onClick={()=>{
          const matchTech = TECHS.find(tt => tt.n === v4DrillTech || tt._code === v4DrillTech);
          if (matchTech) {
            setV3T({...matchTech, segSz: matchTech.sz?.[seg] || 0});
            setV3P(matchTech.p);
          }
          setView(3);
        }} style={{padding:"3px 9px",borderRadius:"5px",border:`1px solid ${t.acc}40`,background:"transparent",color:t.acc,fontSize:"10px",cursor:"pointer",fontWeight:600}}>
          ← View 3: market position
        </button>
      </div>}

      {/* ── V3↔V4 continuity strip: technologies in this pillar as mini-bubbles ── */}
      {v4Mode==="overview" && techs.length>0 && (()=>{
        const stripW = 800, stripH = 110;
        const sorted = [...techs].sort((a,b)=>(parseFloat(b.fy25)||0)-(parseFloat(a.fy25)||0));
        const maxSz = parseFloat(sorted[0]?.fy25)||1;
        return <div style={{...card({padding:"10px 14px",marginBottom:"14px"})}}>
          <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:"6px"}}>
            <div>
              <div style={{fontSize:"11px",color:t.c2,fontWeight:700,letterSpacing:"0.04em"}}>
                ◉ {v4Pillar.toUpperCase()} TECHNOLOGIES · {SEGS[seg]?.s} · {techs.length} techs in this segment
              </div>
              <div style={{fontSize:"9px",color:t.c3,marginTop:"2px"}}>
                ranked by FY25 market size · color = CAGR velocity · same source as View 3 scatter
              </div>
            </div>
            <span style={{fontSize:"9.5px",padding:"3px 8px",borderRadius:"10px",background:`${pc}15`,color:pc,fontWeight:600}}>
              Click any bubble → drill into competitor breakdown
            </span>
          </div>
          <svg width="100%" viewBox={`0 0 ${stripW} ${stripH}`} style={{display:"block"}}>
            {sorted.map((tech,i)=>{
              const sz = parseFloat(tech.fy25)||0;
              const cagr = parseFloat(tech.cagr)||0;
              const r = Math.max(7, Math.min(22, 7 + (sz/maxSz)*15));
              const cx = 30 + (i / Math.max(sorted.length-1,1)) * (stripW - 60);
              const cy = stripH/2 + 6;
              // Match V3 encoding: fill = velocity color, border = pillar color
              const velColor = cagr >= 15 ? "#22c55e" : cagr >= 5 ? "#f59e0b" : cagr < 0 ? "#ef4444" : "#3b82f6";
              // Use single source of truth from top of file
              const pillarBorderColor = PILLAR_COLORS[v4Pillar] || velColor;
              const isSel = v4DrillTech === tech.code;
              return <g key={tech.code} style={{cursor:"pointer"}}
                onClick={()=>{setV4Mode("drilldown");setV4DrillTech(tech.code);}}>
                <title>{tech.name} · ₹{sz} Cr · CAGR {cagr}%</title>
                {isSel && <circle cx={cx} cy={cy} r={r+5} fill="none" stroke={pc} strokeWidth={2} opacity={0.7}/>}
                <circle cx={cx} cy={cy} r={r} fill={`${velColor}${dk?"40":"25"}`} stroke={pillarBorderColor} strokeWidth={2}/>
                <text x={cx} y={cy-r-3} fill={t.c} fontSize="7.5" textAnchor="middle" fontWeight="600">
                  {tech.name.length>14?tech.name.slice(0,12)+"\u2026":tech.name}
                </text>
                <text x={cx} y={cy+r+10} fill={t.c2} fontSize="7" textAnchor="middle" fontWeight="600">
                  {fmt(sz, curr)}
                </text>
                <text x={cx} y={cy+r+18} fill={pillarBorderColor} fontSize="6.5" textAnchor="middle" opacity={0.85}>
                  CAGR {cagr}%
                </text>
              </g>;
            })}
          </svg>
        </div>;
      })()}

      {/* Metrics row */}
      <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:"10px",marginBottom:"14px"}}>
        {[
          {l:v4Mode==="drilldown"&&td?td.tech_name:`${v4Pillar} pillar`,
           v:v4Mode==="drilldown"&&td?fmt(td.cross_segments?.[seg]||0):fmt(d.market_total_fy25_cr),
           n:"FY25 Market"},
          {l:"Projected FY30",
           v:v4Mode==="drilldown"&&td?fmtFy30(td.cross_segments?.[seg],td.cagr):fmt(d.market_fy30_cr),
           n:"FY25 \u00d7 (1+CAGR)\u2075"},
          {l:"CAGR (FY25\u201330)",
           v:`${v4Mode==="drilldown"&&td?td.cagr:d.avg_cagr}%`,
           n:"Weighted average"},
          {l:"Active players",
           v:v4Mode==="drilldown"&&td?td.players?.length||0:d.player_count,
           n:"India-active (OEM supply)"},
        ].map((m,i)=>(
          <div key={i} style={{background:t.btn,borderRadius:"8px",padding:"10px 12px"}}>
            <div style={{fontSize:"10px",color:t.c3}}>{m.l}</div>
            <div style={{fontSize:"20px",fontWeight:600,color:i===2?pc:t.c,marginTop:"2px"}}>{m.v}</div>
            <div style={{fontSize:"9px",color:t.c3,marginTop:"2px"}}>{m.n}</div>
          </div>
        ))}
      </div>

      {/* ═══ OVERVIEW MODE ═══ */}
      {v4Mode==="overview"&&(
        <div style={{display:"grid",gridTemplateColumns:"1fr 340px",gap:"14px"}}>
          {/* Left column */}
          <div>
            {/* Market share bars */}
            <div style={card()}>
              <div style={{fontSize:"13px",fontWeight:600,color:t.c,marginBottom:"12px",display:"flex",alignItems:"center",gap:"6px"}}>
                Market Players &mdash; {v4Pillar} &middot; {SEGS[seg]?.s}
                <span style={{fontSize:"8px",padding:"2px 6px",borderRadius:"4px",background:"#fecaca",color:"#991b1b"}}>AI Estimate</span>
              </div>
              {players.map((p,i)=>{
                const share=parseFloat(p.market_share_pct||0);
                const rev=parseFloat(p.revenue_cr||0);
                const c=barColors[i%barColors.length];
                return(<div key={p.code||i} style={{marginBottom:"10px"}}>
                  <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:"3px"}}>
                    <div style={{display:"flex",alignItems:"center",gap:"6px"}}>
                      <span style={{fontSize:"13px",fontWeight:600,color:t.c}}>{p.short_name||p.name}</span>
                      <span style={{fontSize:"9px",padding:"1px 5px",borderRadius:"4px",background:t.btn,color:t.c3}}>{p.tier||"Tier-1"}</span>
                    </div>
                    <span style={{fontSize:"14px",fontWeight:700,color:pc}}>{share}%</span>
                  </div>
                  <div style={{height:"8px",background:t.btn,borderRadius:"4px",overflow:"hidden"}}>
                    <div style={{height:"100%",width:`${share}%`,background:c,borderRadius:"4px",transition:"width 0.5s ease"}}/>
                  </div>
                  <div style={{fontSize:"9px",color:t.c3,marginTop:"2px"}}>{fmt(rev)}</div>
                </div>);
              })}
            </div>

            {/* Technology grid */}
            <div style={{...card(),marginTop:"12px"}}>
              <div style={{fontSize:"13px",fontWeight:600,color:t.c,marginBottom:"10px"}}>
                Technologies in {v4Pillar}
                <span style={{fontSize:"10px",color:t.c3,fontWeight:400,marginLeft:6}}>Click to drill down &#8599;</span>
              </div>
              <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"8px"}}>
                {techs.map((tech,i)=>{
                  const fy25=parseFloat(tech.fy25||0);
                  const cagr=parseFloat(tech.cagr||0);
                  return(<div key={tech.code||i} onClick={()=>{setV4Mode("drilldown");setV4DrillTech(tech.code);}}
                    style={{background:t.btn,borderRadius:"8px",padding:"10px 12px",cursor:"pointer",border:`1px solid ${t.border}`,transition:"border-color 0.15s"}}
                    onMouseEnter={e=>e.currentTarget.style.borderColor=pc}
                    onMouseLeave={e=>e.currentTarget.style.borderColor=t.border}>
                    <div style={{fontSize:"11px",fontWeight:600,color:t.c,marginBottom:"4px"}}>{tech.name}</div>
                    <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline"}}>
                      <div>
                        <span style={{fontSize:"10px",color:t.c3,textTransform:"lowercase"}}>{tech.maturity}</span>
                        <div style={{fontSize:"13px",fontWeight:600,color:t.c}}>{fmt(fy25)}</div>
                      </div>
                      <div style={{textAlign:"right"}}>
                        <div style={{fontSize:"12px",fontWeight:600,color:cagr>20?"#22c55e":cagr>10?pc:cagr<0?"#ef4444":t.c2}}>{cagr}% CAGR</div>
                      </div>
                    </div>
                  </div>);
                })}
              </div>
            </div>
          </div>

          {/* Right column */}
          <div>
            <div style={card()}>
              <div style={{fontSize:"12px",fontWeight:600,color:t.c,marginBottom:"10px"}}>Key Players &middot; {v4Pillar} &middot; India</div>
              {players.slice(0,8).map((p,i)=>{
                const c=barColors[i%barColors.length];
                return(<div key={p.code||i} style={{display:"flex",alignItems:"center",gap:"8px",padding:"7px 0",borderBottom:`1px solid ${t.border}`}}>
                  <div style={{width:32,height:32,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",fontSize:"11px",fontWeight:600,flexShrink:0,background:`${c}15`,color:c}}>
                    {(p.short_name||p.name||"?")[0]}
                  </div>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{fontSize:"11px",fontWeight:600,color:t.c}}>{p.name}</div>
                    <div style={{fontSize:"9px",color:t.c3,lineHeight:1.3,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>{p.key_products}</div>
                    <div style={{fontSize:"8px",color:t.c3}}>{p.india_presence}</div>
                  </div>
                  <div style={{fontSize:"14px",fontWeight:700,color:pc,flexShrink:0}}>{parseFloat(p.market_share_pct||0)}%</div>
                </div>);
              })}
            </div>

            <div style={{...card(),marginTop:"10px"}}>
              <div style={{fontSize:"12px",fontWeight:600,color:t.c,marginBottom:"8px"}}>Competitive Dynamics</div>
              <div style={{fontSize:"10px",color:t.c2,lineHeight:1.6}}>
                <div style={{marginBottom:"6px"}}><span style={{fontWeight:600,color:t.c}}>AEB mandate (Apr 2026)</span> compresses supplier qualification timelines. Bosch&apos;s integrated radar+camera+iBooster stack gives 6-month lead.</div>
                <div style={{marginBottom:"6px"}}><span style={{fontWeight:600,color:t.c}}>Localisation pressure</span> under PLI favours players with India manufacturing.</div>
                <div><span style={{fontWeight:600,color:t.c}}>Startup entry</span> at L2 camera level threatens commoditisation. Differentiation moves to sensor fusion and L3 stacks.</div>
              </div>
            </div>

            <div style={{...card(),marginTop:"10px",background:`${pc}06`,border:`1px dashed ${pc}30`}}>
              <div style={{fontSize:"10px",fontWeight:600,color:pc,marginBottom:"4px"}}>&#128203; Data Sources</div>
              <div style={{fontSize:"9px",color:t.c3,lineHeight:1.5}}>
                Market shares are AI-estimated from public annual reports, OEM supplier announcements, Bharat NCAP test attributions, and ACMA member records. Technology sizes from platform seed data (View 3).
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ═══ DRILL-DOWN MODE ═══ */}
      {v4Mode==="drilldown"&&(
        <div>
          {/* Tech selector tabs */}
          <div style={{display:"flex",gap:"5px",flexWrap:"wrap",marginBottom:"14px"}}>
            {techs.map((tech,i)=>(
              <button key={tech.code||i} onClick={()=>setV4DrillTech(tech.code)}
                style={{fontSize:"10px",padding:"5px 10px",borderRadius:"6px",cursor:"pointer",
                  fontWeight:v4DrillTech===tech.code?700:400,
                  background:v4DrillTech===tech.code?pc:"transparent",
                  color:v4DrillTech===tech.code?"#fff":t.c2,
                  border:`1px solid ${v4DrillTech===tech.code?pc:t.border}`}}>
                {tech.name} &middot; {fmt(parseFloat(tech.fy25||0))}
              </button>
            ))}
          </div>

          {td&&td.players?.length>0?(
            <div style={{display:"grid",gridTemplateColumns:"1fr 300px",gap:"14px"}}>
              {/* Left */}
              <div>
                <div style={card()}>
                  <div style={{fontSize:"13px",fontWeight:600,color:t.c,marginBottom:"12px",display:"flex",alignItems:"center",gap:"6px"}}>
                    Market Share &middot; {td.tech_name} &middot; {SEGS[seg]?.s}
                    <span style={{fontSize:"8px",padding:"2px 6px",borderRadius:"4px",background:"#fecaca",color:"#991b1b"}}>AI Estimate</span>
                  </div>
                  {(td.players||[]).map((p,i)=>{
                    const share=parseFloat(p.market_share_pct||0);
                    const rev=parseFloat(p.revenue_cr||0);
                    const c=barColors[i%barColors.length];
                    return(<div key={i} style={{marginBottom:"10px"}}>
                      <div style={{display:"flex",justifyContent:"space-between",alignItems:"baseline",marginBottom:"3px"}}>
                        <span style={{fontSize:"12px",fontWeight:600,color:t.c}}>{p.name||p.short_name}</span>
                        <span style={{fontSize:"13px",fontWeight:700,color:pc}}>{share}%</span>
                      </div>
                      <div style={{height:"8px",background:t.btn,borderRadius:"4px",overflow:"hidden"}}>
                        <div style={{height:"100%",width:`${share}%`,background:c,borderRadius:"4px"}}/>
                      </div>
                      <div style={{fontSize:"9px",color:t.c3,marginTop:"2px"}}>{fmt(rev)}
                        {p.strength&&p.strength!=="present"&&<span style={{marginLeft:6,fontWeight:600,color:p.strength==="dominant"?"#22c55e":p.strength==="strong"?pc:"#64748b"}}>&middot; {p.strength}</span>}
                      </div>
                    </div>);
                  })}
                </div>

                {td.cross_segments&&(
                  <div style={{...card(),marginTop:"12px"}}>
                    <div style={{fontSize:"12px",fontWeight:600,color:t.c,marginBottom:"8px"}}>Cross-segment distribution &middot; {td.tech_name}</div>
                    {(()=>{
                      const segColors={"4W_PV":"#185FA5","LCV":"#1D9E75","HCV":"#BA7517","2W":"#D85A30","3W":"#534AB7","Tractor":"#888780"};
                      const cs=td.cross_segments;
                      const total=Object.values(cs).reduce((a,b)=>a+b,0);
                      if(total===0)return <div style={{color:t.c3,fontSize:11}}>No cross-segment data</div>;
                      return(<div>
                        <div style={{height:24,display:"flex",borderRadius:"4px",overflow:"hidden",marginBottom:"6px"}}>
                          {Object.entries(cs).filter(([,v])=>v>0).map(([s,v])=>(
                            <div key={s} style={{width:`${v/total*100}%`,height:"100%",display:"flex",alignItems:"center",justifyContent:"center",fontSize:"8px",fontWeight:600,color:"#fff",background:segColors[s],minWidth:v/total>0.06?30:0}}>
                              {v/total>0.08?`${SEGS[s]?.s||s} ${fmt(v)}`:""}
                            </div>
                          ))}
                        </div>
                        <div style={{display:"flex",flexWrap:"wrap",gap:"8px",fontSize:"9px",color:t.c3}}>
                          {Object.entries(cs).filter(([,v])=>v>0).map(([s,v])=>(
                            <div key={s} style={{display:"flex",alignItems:"center",gap:"3px"}}>
                              <div style={{width:8,height:8,borderRadius:2,background:segColors[s]}}/>
                              {SEGS[s]?.s||s} {fmt(v)} ({Math.round(v/total*100)}%)
                            </div>
                          ))}
                        </div>
                      </div>);
                    })()}
                  </div>
                )}

                {td.oem_sourcing&&td.oem_sourcing.length>0&&(
                  <div style={{...card(),marginTop:"12px"}}>
                    <div style={{fontSize:"12px",fontWeight:600,color:t.c,marginBottom:"8px"}}>OEM Sourcing Patterns &middot; {td.tech_name}</div>
                    <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:"6px"}}>
                      {td.oem_sourcing.map((o,i)=>(
                        <div key={i} style={{background:t.btn,padding:"6px 8px",borderRadius:"6px"}}>
                          <div style={{fontSize:"10px",fontWeight:600,color:t.c}}>{o.oem_name}</div>
                          <div style={{fontSize:"9px",color:t.c3,marginTop:"1px"}}>{o.supplier_codes}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Right */}
              <div>
                <div style={card()}>
                  <div style={{fontSize:"12px",fontWeight:600,color:t.c,marginBottom:"8px"}}>Player Details &middot; {td.tech_name}</div>
                  {(td.players||[]).map((p,i)=>{
                    const c=barColors[i%barColors.length];
                    return(<div key={i} style={{display:"flex",alignItems:"center",gap:"8px",padding:"6px 0",borderBottom:`1px solid ${t.border}`}}>
                      <div style={{width:26,height:26,borderRadius:"50%",display:"flex",alignItems:"center",justifyContent:"center",fontSize:"10px",fontWeight:600,flexShrink:0,background:`${c}15`,color:c}}>
                        {(p.name||p.short_name||"?")[0]}
                      </div>
                      <div style={{flex:1}}>
                        <div style={{fontSize:"11px",fontWeight:600,color:t.c}}>{p.name||p.short_name}</div>
                        <div style={{fontSize:"9px",color:t.c3}}>{fmt(parseFloat(p.revenue_cr||0))} &middot; {parseFloat(p.market_share_pct||0)}% share</div>
                      </div>
                      <div style={{fontSize:"13px",fontWeight:700,color:pc,flexShrink:0}}>{parseFloat(p.market_share_pct||0)}%</div>
                    </div>);
                  })}
                </div>

                <div style={{...card(),marginTop:"10px",background:"#f0fdf4",border:"1px solid #bbf7d0"}}>
                  <div style={{fontSize:"10px",fontWeight:600,color:"#166534",marginBottom:"4px"}}>&#128203; Data Transparency</div>
                  <div style={{fontSize:"9px",color:"#15803d",lineHeight:1.6}}>
                    Market size: <strong>{td.confidence==="high"?"Published":"Derived/Estimated"}</strong>
                    {td.source_note&&` from ${td.source_note.replace(/^(Published:|Derived from)\s*/i,"")}`}
                    <br/>Competitor shares: <strong>AI estimated</strong> from public filings, OEM announcements
                    <br/>FY30 projection: FY25 &times; (1+CAGR)&sup5; formula
                  </div>
                </div>
              </div>
            </div>
          ):(
            <div style={{textAlign:"center",padding:40,color:t.c3}}>
              <div style={{fontSize:24,marginBottom:8}}>&#128070;</div>
              <div>Select a technology tab above to see per-component competitor breakdown</div>
            </div>
          )}
        </div>
      )}
    </div>);
  };
  /* ═══ MAIN RENDER ═══ */
  return(
    <div style={{minHeight:"100vh",background:t.bg,color:t.c,fontFamily:"'DM Sans',system-ui,sans-serif",padding:"18px 24px",transition:"all .3s"}}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet"/>
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"flex-start",marginBottom:"14px",flexWrap:"wrap",gap:"6px"}}>
        <div>
          <h1 style={{margin:0,fontSize:"21px",fontWeight:700,letterSpacing:"-0.02em"}}>Mobility Solutions Intelligence</h1>
          <div style={{fontSize:"11px",color:t.c2,marginTop:"2px"}}>Indian Auto Component Industry · {curr==="INR"?"₹6.73 Lakh Crore ($80.2B)":"€75.6B ($80.2B)"} FY25 · ACMA Verified · Showing: <strong style={{color:t.acc}}>{SEGS[seg].l}</strong> · {SEGS[seg].u} · {SEGS[seg].src} · <span style={{padding:"2px 6px",borderRadius:"4px",fontSize:"9px",fontWeight:700,background:apiStatus==="live"?"#22c55e20":"#f9731620",color:apiStatus==="live"?"#22c55e":"#f97316",border:`1px solid ${apiStatus==="live"?"#22c55e40":"#f9731640"}`}}>{apiStatus==="live"?`● LIVE API${lastRefresh?" · "+lastRefresh:""}`:apiStatus==="loading"?"◌ Connecting...":"○ Offline — Fallback Data"}</span></div>
        </div>
        <div style={{display:"flex",gap:"4px",alignItems:"center",flexWrap:"wrap"}}>
          <button onClick={()=>setDk(!dk)} style={{padding:"4px 10px",borderRadius:"6px",border:`1px solid ${t.border}`,background:t.btn,color:t.c2,fontSize:"11px",cursor:"pointer"}}>{dk?"☀ Light":"🌙 Dark"}</button>
          <button onClick={()=>setCurr(c=>c==="INR"?"EUR":"INR")}
            title={eurRateMeta?`1 EUR = \u20b9${liveEurRate.toFixed(2)} \u00b7 ${eurRateMeta.source} \u00b7 ${eurRateMeta.fetched_at}`:`1 EUR = \u20b9${liveEurRate.toFixed(2)}`}
            style={{padding:"4px 10px",borderRadius:"6px",border:`1px solid ${curr==="EUR"?t.acc:t.border}`,background:curr==="EUR"?`${t.acc}18`:t.btn,color:curr==="EUR"?t.acc:t.c2,fontSize:"11px",fontWeight:600,cursor:"pointer"}}>{curr==="INR"?"₹ INR":"€ EUR"}</button>
          <span style={{fontSize:"9.5px",color:t.c3,fontStyle:"italic",alignSelf:"center"}}>
            1 EUR = ₹{liveEurRate.toFixed(2)}{eurRateMeta?.fetched_at && eurRateMeta.fetched_at !== "fallback" ? ` (${eurRateMeta.fetched_at})` : ""}
          </span>
          {Object.entries(SEGS).map(([k,v])=><button key={k} onClick={()=>{setSeg(k);setV1Sel(null);setV1Compare([]);setV1Baseline("now");setV2Pil(null);setV3T(null);setV4Mode("overview");setV4DrillTech(null);setV4Data(null);setAiAnalysis(null);}} style={{padding:"4px 9px",borderRadius:"6px",border:`1px solid ${k===seg?t.acc:t.border}`,background:k===seg?`${t.acc}18`:t.btn,color:k===seg?t.acc:t.c2,fontSize:"11px",fontWeight:600,cursor:"pointer"}}>{v.ic} {v.s}</button>)}
        </div>
      </div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr 1fr 1fr",gap:"6px",marginBottom:"14px"}}>
        {[[1,"View 1: PESTEL Risk Map","Likelihood × Impact · Trend Analysis"],[2,"View 2: Technology Stack","Bosch Tech Stack · Growth Drivers"],[3,"View 3: Market Landscape","CAGR × Market Size · Growth Projection"],[4,"View 4: Competitor Landscape","Market Share · Players · Technologies"]].map(([v,ti,su])=>(
          <div key={v} onClick={()=>{setView(v);setV3T(null);setV1Sel(null);setAiAnalysis(null);}} style={{padding:"10px 14px",borderRadius:"10px",cursor:"pointer",border:`2px solid ${view===v?t.acc:t.border}`,background:view===v?`${t.acc}08`:t.card}}>
            <div style={{fontSize:"13px",fontWeight:700,color:view===v?t.acc:t.c}}>{ti}</div>
            <div style={{fontSize:"10px",color:t.c3,marginTop:"1px"}}>{su}</div>
          </div>
        ))}
      </div>
      {view===1&&renderV1()}{view===2&&renderV2()}{view===3&&renderV3()}{view===4&&renderV4()}
      <div style={{marginTop:"16px",padding:"8px 0",borderTop:`1px solid ${t.border}`,display:"flex",justifyContent:"space-between",alignItems:"center",fontSize:"9px",color:t.c3,flexWrap:"wrap",gap:"4px"}}>
        <span>Sources: ACMA FY25 · SIAM CY25 · Mordor Intelligence Jan 2026 · ICRA Sep 2025 · Vahan Dashboard · IBEF Jan 2026 · MoCI · MoRTH</span>
        {/* Source check + Sanity engine badges hidden for demo. To re-enable, restore commented blocks below. */}
        {/*
        {validationStats&&validationStats.total>0&&<span ...>🔍 Source check ...</span>}
        {auditStats&&<span ...>🛡️ Sanity engine ...</span>}
        */}
        {healthData&&<span style={{color:healthData.status==="healthy"?"#22c55e":t.c3,fontWeight:600}}>● {healthData.status}</span>}
      </div>
    </div>
  );
}
