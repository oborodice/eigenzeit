(
// 値が飛んだときにプツッという音が出ないよう、この時間をかけて滑らかに変える
var smoothingSeconds = 0.1;

s.waitForBoot {
	var sine;

	SynthDef(\sine, { |freq = 440, amp = 0|
		// 想定外の値が届いても耳やスピーカーを傷めないよう、周波数は人が聞こえる範囲に、音量は取り決めの範囲に収める
		var smoothedFreq = freq.clip(20, 20000).lag(smoothingSeconds);
		var smoothedAmp = amp.clip(0, 1).lag(smoothingSeconds);
		Out.ar(0, SinOsc.ar(smoothedFreq) * smoothedAmp ! 2);
	}).add;

	// SynthDefの登録はサーバー側で後から行われるため、終わるのを待ってから鳴らす
	s.sync;

	sine = Synth(\sine);

	OSCdef(\sine, { |msg|
		sine.set(\freq, msg[1], \amp, msg[2]);
	}, '/sine');
};
)
