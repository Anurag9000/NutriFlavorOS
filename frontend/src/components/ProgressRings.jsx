"""
Animated Progress Rings Component(Apple Watch Style)
Beautiful, fluid animations for daily nutrition goals
"""
import React, { useEffect, useState } from 'react';
import { motion } from 'framer-motion';

const ProgressRing = ({
    percentage,
    color,
    label,
    size = 120,
    strokeWidth = 12
}) => {
    const [animatedPercentage, setAnimatedPercentage] = useState(0);

    useEffect(() => {
        // Animate from 0 to target percentage
        const timer = setTimeout(() => {
            setAnimatedPercentage(percentage);
        }, 100);
        return () => clearTimeout(timer);
    }, [percentage]);

    const radius = (size - strokeWidth) / 2;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (animatedPercentage / 100) * circumference;

    // Pulse animation when close to goal (90%+)
    const shouldPulse = percentage >= 90 && percentage < 100;
    const isComplete = percentage >= 100;

    return (
        <div className="progress-ring-container" style={{ position: 'relative', width: size, height: size }}>
            <svg width={size} height={size}>
                {/* Background circle */}
                <circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke="rgba(255, 255, 255, 0.1)"
                    strokeWidth={strokeWidth}
                />

                {/* Progress circle */}
                <motion.circle
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    stroke={color}
                    strokeWidth={strokeWidth}
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                    transform={`rotate(-90 ${size / 2} ${size / 2})`}
                    initial={{ strokeDashoffset: circumference }}
                    animate={{
                        strokeDashoffset: offset,
                        filter: shouldPulse ? [
                            'drop-shadow(0 0 0px ' + color + ')',
                            'drop-shadow(0 0 10px ' + color + ')',
                            'drop-shadow(0 0 0px ' + color + ')'
                        ] : 'drop-shadow(0 0 0px ' + color + ')'
                    }}
                    transition={{
                        strokeDashoffset: { duration: 1, ease: 'easeOut' },
                        filter: { duration: 1.5, repeat: shouldPulse ? Infinity : 0 }
                    }}
                    style={{
                        filter: isComplete ? `drop-shadow(0 0 15px ${color})` : 'none'
                    }}
                />
            </svg>

            {/* Center text */}
            <div style={{
                position: 'absolute',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                textAlign: 'center'
            }}>
                <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: isComplete ? [1, 1.2, 1] : 1 }}
                    transition={{ duration: 0.5 }}
                    style={{
                        fontSize: '24px',
                        fontWeight: 'bold',
                        color: 'white'
                    }}
                >
                    {Math.round(percentage)}%
                </motion.div>
                <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)' }}>
                    {label}
                </div>
            </div>

            {/* Confetti on completion */}
            {isComplete && (
                <motion.div
                    initial={{ opacity: 0, scale: 0 }}
                    animate={{ opacity: [0, 1, 0], scale: [0, 1.5, 2] }}
                    transition={{ duration: 1 }}
                    style={{
                        position: 'absolute',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        fontSize: '48px'
                    }}
                >
                    🎉
                </motion.div>
            )}
        </div>
    );
};

export const DailyGoalsRings = ({ healthScore, tasteScore, varietyScore, sustainabilityScore }) => {
    return (
        <div className="daily-goals-container" style={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            padding: '20px',
            background: 'linear-gradient(135deg, rgba(0,0,0,0.2), rgba(0,0,0,0.1))',
            borderRadius: '20px',
            backdropFilter: 'blur(10px)'
        }}>
            <h2 style={{ color: 'white', marginBottom: '20px' }}>Today's Goals</h2>

            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '30px',
                marginBottom: '20px'
            }}>
                <ProgressRing
                    percentage={healthScore * 100}
                    color="#10b981"
                    label="Health"
                />
                <ProgressRing
                    percentage={tasteScore * 100}
                    color="#8b5cf6"
                    label="Taste"
                />
                <ProgressRing
                    percentage={varietyScore * 100}
                    color="#f59e0b"
                    label="Variety"
                />
                <ProgressRing
                    percentage={sustainabilityScore * 100}
                    color="#3b82f6"
                    label="Eco"
                />
            </div>

            {/* Motivational message */}
            <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 1 }}
                style={{
                    color: 'rgba(255, 255, 255, 0.8)',
                    fontSize: '14px',
                    textAlign: 'center'
                }}
            >
                {getMotivationalMessage(healthScore, tasteScore, varietyScore, sustainabilityScore)}
            </motion.div>
        </div>
    );
};

function getMotivationalMessage(health, taste, variety, sustainability) {
    const avg = (health + taste + variety + sustainability) / 4;

    if (avg >= 0.95) return "Perfect day! You're crushing it! 💪";
    if (avg >= 0.85) return "Almost there! 2 more meals to perfection! 🌟";
    if (avg >= 0.70) return "Great progress! Keep going! 🚀";
    if (avg >= 0.50) return "You're on track! 👍";
    return "Let's make today amazing! 🌱";
}

export default DailyGoalsRings;
