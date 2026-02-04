"""
AR Meal Scanning Component
Point camera at food → Instant AR nutrition overlay
"""
import React, { useRef, useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export const ARMealScanner = ({ onMealDetected }) => {
    const videoRef = useRef(null);
    const canvasRef = useRef(null);
    const [isScanning, setIsScanning] = useState(false);
    const [detectedMeal, setDetectedMeal] = useState(null);
    const [cameraActive, setCameraActive] = useState(false);

    useEffect(() => {
        if (cameraActive) {
            startCamera();
        }
        return () => {
            stopCamera();
        };
    }, [cameraActive]);

    const startCamera = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: 'environment' } // Use back camera on mobile
            });
            if (videoRef.current) {
                videoRef.current.srcObject = stream;
            }
        } catch (err) {
            console.error('Camera access denied:', err);
        }
    };

    const stopCamera = () => {
        if (videoRef.current && videoRef.current.srcObject) {
            const tracks = videoRef.current.srcObject.getTracks();
            tracks.forEach(track => track.stop());
        }
    };

    const scanMeal = async () => {
        setIsScanning(true);

        // Capture frame from video
        const canvas = canvasRef.current;
        const video = videoRef.current;
        const context = canvas.getContext('2d');

        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);

        // Convert to blob and send to backend
        canvas.toBlob(async (blob) => {
            const formData = new FormData();
            formData.append('image', blob);

            try {
                const response = await fetch('/api/v1/vision/detect_meal', {
                    method: 'POST',
                    body: formData
                });

                const result = await response.json();
                setDetectedMeal(result);
                setIsScanning(false);

                // Haptic feedback
                if (navigator.vibrate) {
                    navigator.vibrate(200);
                }
            } catch (err) {
                console.error('Meal detection failed:', err);
                setIsScanning(false);
            }
        });
    };

    return (
        <div className="ar-scanner-container" style={{
            position: 'relative',
            width: '100%',
            height: '100vh',
            background: '#000'
        }}>
            {/* Camera feed */}
            <video
                ref={videoRef}
                autoPlay
                playsInline
                style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover'
                }}
            />

            {/* Hidden canvas for capture */}
            <canvas ref={canvasRef} style={{ display: 'none' }} />

            {/* AR Overlay */}
            <AnimatePresence>
                {detectedMeal && (
                    <ARNutritionOverlay
                        meal={detectedMeal}
                        onClose={() => setDetectedMeal(null)}
                        onLog={() => {
                            onMealDetected(detectedMeal);
                            setDetectedMeal(null);
                        }}
                    />
                )}
            </AnimatePresence>

            {/* Scan button */}
            <motion.button
                whileTap={{ scale: 0.9 }}
                onClick={scanMeal}
                disabled={isScanning}
                style={{
                    position: 'absolute',
                    bottom: '40px',
                    left: '50%',
                    transform: 'translateX(-50%)',
                    width: '80px',
                    height: '80px',
                    borderRadius: '50%',
                    background: isScanning
                        ? 'linear-gradient(135deg, #F59E0B, #D97706)'
                        : 'linear-gradient(135deg, #10B981, #059669)',
                    border: '4px solid white',
                    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.3)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '32px'
                }}
            >
                {isScanning ? '⏳' : '📸'}
            </motion.button>

            {/* Scanning animation */}
            {isScanning && (
                <motion.div
                    initial={{ scaleX: 0 }}
                    animate={{ scaleX: 1 }}
                    transition={{ duration: 1.5, repeat: Infinity }}
                    style={{
                        position: 'absolute',
                        top: '50%',
                        left: 0,
                        right: 0,
                        height: '2px',
                        background: 'linear-gradient(90deg, transparent, #10B981, transparent)',
                        transformOrigin: 'left'
                    }}
                />
            )}

            {/* Instructions */}
            <div style={{
                position: 'absolute',
                top: '40px',
                left: '50%',
                transform: 'translateX(-50%)',
                background: 'rgba(0, 0, 0, 0.6)',
                padding: '10px 20px',
                borderRadius: '20px',
                color: 'white',
                fontSize: '14px',
                backdropFilter: 'blur(10px)'
            }}>
                Point camera at your meal
            </div>
        </div>
    );
};

const ARNutritionOverlay = ({ meal, onClose, onLog }) => {
    return (
        <motion.div
            initial={{ opacity: 0, y: 50 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 50 }}
            style={{
                position: 'absolute',
                bottom: '140px',
                left: '20px',
                right: '20px',
                background: 'rgba(0, 0, 0, 0.85)',
                borderRadius: '20px',
                padding: '20px',
                backdropFilter: 'blur(20px)',
                border: '1px solid rgba(255, 255, 255, 0.1)'
            }}
        >
            {/* Meal name with icon */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                marginBottom: '15px'
            }}>
                <span style={{ fontSize: '32px', marginRight: '10px' }}>
                    {meal.emoji || '🍽️'}
                </span>
                <div>
                    <h3 style={{ color: 'white', margin: 0, fontSize: '20px' }}>
                        {meal.name}
                    </h3>
                    <p style={{ color: 'rgba(255, 255, 255, 0.6)', margin: 0, fontSize: '12px' }}>
                        {meal.confidence}% confidence
                    </p>
                </div>
            </div>

            {/* Nutrition grid */}
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '10px',
                marginBottom: '15px'
            }}>
                <NutritionBadge label="Calories" value={meal.calories} unit="kcal" />
                <NutritionBadge label="Protein" value={meal.protein} unit="g" />
                <NutritionBadge label="Carbs" value={meal.carbs} unit="g" />
                <NutritionBadge label="Fat" value={meal.fat} unit="g" />
            </div>

            {/* Score bars */}
            <div style={{ marginBottom: '15px' }}>
                <ScoreBar label="Health" score={meal.health_score} color="#10B981" />
                <ScoreBar label="Taste" score={meal.taste_score} color="#8B5CF6" />
            </div>

            {/* Action buttons */}
            <div style={{ display: 'flex', gap: '10px' }}>
                <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={onLog}
                    style={{
                        flex: 1,
                        padding: '12px',
                        borderRadius: '10px',
                        background: 'linear-gradient(135deg, #10B981, #059669)',
                        color: 'white',
                        border: 'none',
                        fontWeight: 'bold',
                        cursor: 'pointer'
                    }}
                >
                    Log Meal
                </motion.button>
                <motion.button
                    whileTap={{ scale: 0.95 }}
                    onClick={onClose}
                    style={{
                        padding: '12px 20px',
                        borderRadius: '10px',
                        background: 'rgba(255, 255, 255, 0.1)',
                        color: 'white',
                        border: 'none',
                        cursor: 'pointer'
                    }}
                >
                    ✕
                </motion.button>
            </div>
        </motion.div>
    );
};

const NutritionBadge = ({ label, value, unit }) => (
    <div style={{
        background: 'rgba(255, 255, 255, 0.05)',
        borderRadius: '10px',
        padding: '10px',
        textAlign: 'center'
    }}>
        <div style={{ color: 'rgba(255, 255, 255, 0.6)', fontSize: '11px', marginBottom: '4px' }}>
            {label}
        </div>
        <div style={{ color: 'white', fontSize: '18px', fontWeight: 'bold' }}>
            {value}{unit}
        </div>
    </div>
);

const ScoreBar = ({ label, score, color }) => (
    <div style={{ marginBottom: '8px' }}>
        <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: '4px',
            fontSize: '12px'
        }}>
            <span style={{ color: 'rgba(255, 255, 255, 0.7)' }}>{label}</span>
            <span style={{ color: 'white', fontWeight: 'bold' }}>{Math.round(score * 100)}%</span>
        </div>
        <div style={{
            height: '4px',
            background: 'rgba(255, 255, 255, 0.1)',
            borderRadius: '2px',
            overflow: 'hidden'
        }}>
            <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${score * 100}%` }}
                transition={{ duration: 0.8, ease: 'easeOut' }}
                style={{
                    height: '100%',
                    background: color,
                    borderRadius: '2px'
                }}
            />
        </div>
    </div>
);

export default ARMealScanner;
