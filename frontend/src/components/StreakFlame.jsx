"""
Streak Flames Component(Duolingo - inspired)
Visual streak counter with progressive flame animations
"""
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const StreakFlame = ({ streakDays, onTap }) => {
    const [isShaking, setIsShaking] = useState(false);

    // Determine flame type based on streak length
    const getFlameEmoji = () => {
        if (streakDays >= 31) return '⭐🔥'; // Golden flame
        if (streakDays >= 15) return '🌈🔥'; // Rainbow flame
        if (streakDays >= 8) return '💙🔥';  // Blue flame
        if (streakDays >= 4) return '🔥🔥';  // Bigger flame
        return '🔥';                         // Small flame
    };

    const getFlameColor = () => {
        if (streakDays >= 31) return '#FFD700'; // Gold
        if (streakDays >= 15) return '#FF69B4'; // Rainbow pink
        if (streakDays >= 8) return '#3B82F6';  // Blue
        if (streakDays >= 4) return '#F59E0B';  // Orange
        return '#EF4444';                       // Red
    };

    const handleShake = () => {
        setIsShaking(true);
        setTimeout(() => setIsShaking(false), 500);
    };

    return (
        <motion.div
            className="streak-flame-container"
            onClick={onTap}
            onMouseEnter={handleShake}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            animate={isShaking ? {
                rotate: [0, -10, 10, -10, 10, 0],
                transition: { duration: 0.5 }
            } : {}}
            style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                cursor: 'pointer',
                padding: '20px',
                background: `radial-gradient(circle, ${getFlameColor()}22, transparent)`,
                borderRadius: '20px',
                position: 'relative'
            }}
        >
            {/* Flame emoji with animation */}
            <motion.div
                animate={{
                    scale: [1, 1.1, 1],
                    filter: [
                        'drop-shadow(0 0 5px ' + getFlameColor() + ')',
                        'drop-shadow(0 0 15px ' + getFlameColor() + ')',
                        'drop-shadow(0 0 5px ' + getFlameColor() + ')'
                    ]
                }}
                transition={{
                    duration: 2,
                    repeat: Infinity,
                    ease: 'easeInOut'
                }}
                style={{
                    fontSize: '64px',
                    marginBottom: '10px'
                }}
            >
                {getFlameEmoji()}
            </motion.div>

            {/* Streak count */}
            <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                style={{
                    fontSize: '32px',
                    fontWeight: 'bold',
                    color: getFlameColor(),
                    textShadow: `0 0 10px ${getFlameColor()}`
                }}
            >
                {streakDays}
            </motion.div>

            <div style={{
                fontSize: '14px',
                color: 'rgba(255, 255, 255, 0.7)',
                marginTop: '5px'
            }}>
                day streak
            </div>

            {/* Sparkles for golden flame */}
            {streakDays >= 31 && (
                <motion.div
                    animate={{
                        opacity: [0, 1, 0],
                        scale: [0.5, 1, 0.5]
                    }}
                    transition={{
                        duration: 2,
                        repeat: Infinity,
                        delay: 0.5
                    }}
                    style={{
                        position: 'absolute',
                        top: '10px',
                        right: '10px',
                        fontSize: '24px'
                    }}
                >
                    ✨
                </motion.div>
            )}

            {/* Achievement milestone badge */}
            {streakDays % 7 === 0 && streakDays > 0 && (
                <motion.div
                    initial={{ scale: 0, rotate: -180 }}
                    animate={{ scale: 1, rotate: 0 }}
                    style={{
                        position: 'absolute',
                        top: '-10px',
                        right: '-10px',
                        background: getFlameColor(),
                        borderRadius: '50%',
                        width: '30px',
                        height: '30px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '16px',
                        boxShadow: `0 0 20px ${getFlameColor()}`
                    }}
                >
                    🏆
                </motion.div>
            )}
        </motion.div>
    );
};

export const StreakCalendar = ({ streakHistory }) => {
    return (
        <div style={{
            background: 'rgba(0, 0, 0, 0.2)',
            borderRadius: '15px',
            padding: '20px',
            marginTop: '20px'
        }}>
            <h3 style={{ color: 'white', marginBottom: '15px' }}>Streak History</h3>
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(7, 1fr)',
                gap: '8px'
            }}>
                {streakHistory.map((day, index) => (
                    <motion.div
                        key={index}
                        initial={{ scale: 0 }}
                        animate={{ scale: 1 }}
                        transition={{ delay: index * 0.02 }}
                        style={{
                            width: '40px',
                            height: '40px',
                            borderRadius: '8px',
                            background: day.completed
                                ? 'linear-gradient(135deg, #10b981, #059669)'
                                : 'rgba(255, 255, 255, 0.1)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '18px'
                        }}
                    >
                        {day.completed ? '✓' : ''}
                    </motion.div>
                ))}
            </div>
        </div>
    );
};

export const StreakFreeze = ({ freezesAvailable, onBuy }) => {
    return (
        <motion.div
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={onBuy}
            style={{
                background: 'linear-gradient(135deg, #3B82F6, #2563EB)',
                borderRadius: '15px',
                padding: '15px',
                marginTop: '20px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between'
            }}
        >
            <div>
                <div style={{ color: 'white', fontWeight: 'bold', fontSize: '16px' }}>
                    Streak Freeze ❄️
                </div>
                <div style={{ color: 'rgba(255, 255, 255, 0.8)', fontSize: '12px' }}>
                    Protect your streak for 1 day
                </div>
            </div>
            <div style={{
                background: 'rgba(255, 255, 255, 0.2)',
                borderRadius: '10px',
                padding: '8px 15px',
                color: 'white',
                fontWeight: 'bold'
            }}>
                {freezesAvailable} available
            </div>
        </motion.div>
    );
};

export default StreakFlame;
