// クリックの層: 短い音を、等間隔またはランダムな間隔で鳴らし続ける
// main.scdが読み込み、最後の関数に共通の値と処理を渡してSynthDefを作る。OSCのアドレスはSynthDefの名前になる

// 頻度の下限は、AIが音を選び直す間隔の間に1回は鳴る回数にし、選んだ値の効果を観測できるようにする(間隔を変えたら見直す)
// 上限は周波数の上限と揃える。頻度を上げると、クリックがつながって音の高さとして聴こえる
var minRate = 0.1;
// クリック1回は、叩いた物が数回揺れて止まるような、短いサイン波の揺れとして作る
// 明るさはその揺れの周波数で、低いと「コッ」、高いと「チッ」になる
var clickCycles = 3;

{ |smooth, highFreqGain, minFreq, maxFreq|
	// out以外の値は全て0〜1で受け取る。並びがOSCで送る値の順番になる
	SynthDef(\clicks, { |out, rate = 0, irregularity = 0, brightness = 0, amp = 0|
		var clickRate = smooth.(rate).linexp(0, 1, minRate, maxFreq);
		var smoothedIrregularity = smooth.(irregularity);
		var clickFreq = smooth.(brightness).linexp(0, 1, minFreq, maxFreq);
		var smoothedAmp = smooth.(amp);
		var click = { |trigger|
			// 鳴るたびに揺れを最初から始め、クリックごとに音の形が変わらないようにする
			// 値0から始め、鳴った瞬間の跳びで全ての周波数を含むパチッという音が混ざり、明るさの違いが埋もれないようにする
			var wave = sin(Sweep.ar(trigger, clickFreq) * 2pi);
			// 頻度が高く前のクリックが鳴り終わらないうちに次が来ても、足し合わさらず鳴り直すようにする
			wave * EnvGen.ar(Env.perc(0, clickCycles / clickFreq), trigger);
		};
		var regularClicks = click.(Impulse.ar(clickRate));
		// Dustはクリックごとに音量がランダムになるため、鳴ったかどうかだけを使い、不規則さが音量に混ざらないようにする
		var randomClicks = click.(Dust.ar(clickRate) > 0);
		var mixed = (regularClicks * (1 - smoothedIrregularity)) + (randomClicks * smoothedIrregularity);
		// 揺れの周波数か頻度のどちらかが高ければ、高い音として聴こえる
		Out.ar(out, mixed * highFreqGain.(max(clickFreq, clickRate)) * smoothedAmp ! 2);
	});
}
