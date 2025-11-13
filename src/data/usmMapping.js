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


