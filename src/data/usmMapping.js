// ================================
// USM 5 IEG DEFINITIONS
// ================================
export const IEG = {
  IEG1: "Knowledge & Professional Skills",
  IEG2: "Values, Ethics & Humanity",
  IEG3: "Socio-Entrepreneurship & Sustainability",
  IEG4: "Communication",
  IEG5: "Leadership, Teamwork & Lifelong Learning"
};


// ================================
// IEG → PEO Mapping (Your updated)
// ================================
export const IEGtoPEO = {
  IEG1: ["PEO1"],      // Knowledge & Professional Skills
  IEG2: ["PEO2"],      // Values, Ethics, Humanity
  IEG3: ["PEO3"],      // Socio-Entrepreneurship, Sustainability
  IEG4: ["PEO4"],      // Communication
  IEG5: ["PEO5"]       // Leadership, Teamwork, Lifelong Learning
};


// ================================
// PEO → PLO Mapping (Your updated)
// MQF2.0 11 PLO DOMAINS
// ================================
export const PEOtoPLO = {
  PEO1: ["PLO1", "PLO2", "PLO3", "PLO6", "PLO7"],   // Knowledge, Cognitive, Practical, Digital, Numeracy
  PEO2: ["PLO11"],                                  // Leadership & Responsibility
  PEO3: ["PLO10", "PLO9"],                          // Ethics + Entrepreneurship
  PEO4: ["PLO5"],                                   // Communication
  PEO5: ["PLO8", "PLO4", "PLO9"]                    // Personal, Interpersonal, Entrepreneurship
};

"PEOstatements": {
  "Diploma": {
    "PEO1": "Apply foundational disciplinary knowledge and technical skills under supervision in routine tasks.",
    "PEO2": "Demonstrate responsible behaviour, ethical awareness, and basic professionalism.",
    "PEO3": "Participate in community and entrepreneurship activities at an introductory level.",
    "PEO4": "Communicate effectively in simple workplace and team environments.",
    "PEO5": "Show initiative, self-management, and willingness for further learning."
  },
  "Degree": {
    "PEO1": "Apply broad and coherent disciplinary knowledge and analytical skills to solve professional and societal problems.",
    "PEO2": "Demonstrate ethical conduct, integrity, and sensitivity to societal and cultural responsibilities.",
    "PEO3": "Engage in entrepreneurship, innovation, and community initiatives to generate value.",
    "PEO4": "Communicate effectively across professional, social, and multidisciplinary contexts.",
    "PEO5": "Demonstrate leadership, teamwork, autonomy, and commitment to continuous learning."
  },
  "Master": {
    "PEO1": "Synthesize advanced disciplinary knowledge to create, evaluate, and apply solutions in complex situations.",
    "PEO2": "Demonstrate high ethical standards, reflective practice, and professional integrity.",
    "PEO3": "Lead innovative, entrepreneurial, or community-based projects contributing to sustainable development.",
    "PEO4": "Communicate persuasively to diverse audiences, including experts and non-experts.",
    "PEO5": "Demonstrate leadership, autonomy, and continuous professional development aligned with industry expectations."
  },
  "PhD": {
    "PEO1": "Generate original knowledge and contribute to the advancement of the discipline.",
    "PEO2": "Uphold scholarly integrity, ethical leadership, and responsible research conduct.",
    "PEO3": "Lead high-impact initiatives, innovations, or enterprises addressing global challenges.",
    "PEO4": "Communicate complex ideas effectively to academic, professional, and global communities.",
    "PEO5": "Demonstrate thought leadership, autonomy, and lifelong scholarship."
  }
}

