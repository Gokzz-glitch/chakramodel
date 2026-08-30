import React, { useState, useRef, useEffect } from 'react';
import './index.css';

function App() {
  const [sliderPos, setSliderPos] = useState(50);
  const sliderRef = useRef(null);

  const handleMouseMove = (e) => {
    if (!sliderRef.current) return;
    const rect = sliderRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const percent = (x / rect.width) * 100;
    setSliderPos(percent);
  };

  const handleTouchMove = (e) => {
    if (!sliderRef.current) return;
    const rect = sliderRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.touches[0].clientX - rect.left, rect.width));
    const percent = (x / rect.width) * 100;
    setSliderPos(percent);
  };

  return (
    <div className="app-container">
      {/* Hero Section */}
      <section className="hero animate-fade-up">
        <h1 className="text-gradient">ChakraModel AI</h1>
        <p>
          Next-generation polyp segmentation using ViT-Large and Conformal Uncertainty Calibration. 
          Experience real-time, clinical-grade precision that pushes the boundaries of medical AI.
        </p>
        <button className="btn-primary">Request Commercial License</button>
      </section>

      {/* Interactive Showcase */}
      <section className="slider-section animate-fade-up" style={{ animationDelay: '0.2s' }}>
        <h2><span className="text-gradient">Interactive Precision</span> Showcase</h2>
        <p style={{ color: 'var(--text-muted)', marginTop: '1rem' }}>Slide to reveal the AI segmentation mask.</p>
        
        <div 
          className="slider-container" 
          ref={sliderRef} 
          onMouseMove={handleMouseMove}
          onTouchMove={handleTouchMove}
        >
          {/* Base Image (Raw Medical Image) */}
          <div style={{
            position: 'absolute', top: 0, left: 0, width: '100%', height: '100%',
            backgroundColor: '#1a1a2e', display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: '#4facfe', fontSize: '2rem', border: '2px dashed #4facfe'
          }}>
            [Raw Endoscopy Input]
          </div>

          {/* Overlay Image (Segmented Image) */}
          <div className="slider-overlay" style={{ width: `${sliderPos}%` }}>
            <div style={{
              position: 'absolute', top: 0, left: 0, width: '200%', height: '100%',
              backgroundColor: '#0a0e17', display: 'flex', alignItems: 'center', justifyContent: 'center',
              color: '#00f2fe', fontSize: '2rem', border: '2px solid #00f2fe'
            }}>
              [AI Segmentation Mask]
            </div>
          </div>

          {/* Slider Handle */}
          <div className="slider-handle" style={{ left: `${sliderPos}%` }}></div>
        </div>
      </section>

      {/* Features/Metrics Grid */}
      <section className="features-grid animate-fade-up" style={{ animationDelay: '0.4s' }}>
        <div className="feature-card glass-panel">
          <h3>ViT-Large Backbone</h3>
          <p>Powered by vit_large_patch16_384 with 304M parameters, outperforming SOTA models like SAM-2 and PraNet.</p>
        </div>
        <div className="feature-card glass-panel">
          <h3>94.1% DSC Accuracy</h3>
          <p>Unmatched Dice Similarity Coefficient (DSC) delivering pixel-perfect topological mapping for complex polyp structures.</p>
        </div>
        <div className="feature-card glass-panel">
          <h3>Conformal Calibration</h3>
          <p>Inductive Split-Conformal prediction sets guaranteeing statistical safety bounds for clinical decision making.</p>
        </div>
      </section>
    </div>
  );
}

export default App;
