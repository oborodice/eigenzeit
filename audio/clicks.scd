// クリックの層: 短い音を、等間隔またはランダムな間隔で鳴らし続ける
// main.scdが読み込み、最後の関数に共通の値と処理を渡してSynthDefを作る。OSCのアドレスはSynthDefの名前になる

// 頻度の下限は、AIが音を選び直す間隔の間に1回は鳴る回数にし、選んだ値の効果を観測できるようにする(間隔を変えたら見直す)
// 上限は周波数の上限と揃える。頻度を上げると、クリックがつながって音の高さとして聴こえる
var minRate = 0.1;
// クリック1回は、叩いた物が数回揺れて止まるような、短いサイン波の揺れとして作る
// 明るさはその揺れの周波数で、低いと「コッ」、高いと「チッ」になる
var clickCycles = 3;
// 揺れが消えていく曲がり具合(Env.percの既定の値)
var envelopeCurve = -4;
// 等間隔のクリックの並びの、音量を掛ける前の実効値
// クリック1回は sin(ωt) に包絡 (e^(kt) - e^c) / (1 - e^c) (kは曲がり具合を1回の長さで割った値)を掛けた形
// その二乗を、鳴り終わるか次のクリックが来るまで積分し、間隔で割る。sin^2 = (1 - cos 2ωt) / 2 として、指数と余弦の積の積分の公式で求める
var clickTrainRms = { |clickRate, clickFreq|
	var duration = clickCycles / clickFreq;
	var end = duration.min(clickRate.reciprocal);
	var k = envelopeCurve / duration;
	// e^(kt) の、鳴り終わる時点での値
	var endExp = envelopeCurve.exp;
	// cos 2ωt の角周波数 2ω
	var doubleAngularFreq = 4pi * clickFreq;
	// 0からendまでの、e^(αt) cos(2ωt) の積分。αが0なら cos(2ωt) の積分になる
	var expCosIntegral = { |alpha|
		(((alpha * end).exp * ((alpha * cos(doubleAngularFreq * end)) + (doubleAngularFreq * sin(doubleAngularFreq * end)))) - alpha) / (alpha.squared + doubleAngularFreq.squared)
	};
	var expIntegral = { |alpha| ((alpha * end).exp - 1) / alpha };
	var squaredEnvelope = expIntegral.(2 * k) - (2 * endExp * expIntegral.(k)) + (endExp.squared * end);
	var squaredEnvelopeCos = expCosIntegral.(2 * k) - (2 * endExp * expCosIntegral.(k)) + (endExp.squared * expCosIntegral.(0));
	(0.5 * (squaredEnvelope - squaredEnvelopeCos) / (1 - endExp).squared * clickRate).sqrt;
};

{ |smooth, ampToGain, freqGain, layerRms, minFreq, maxFreq|
	// out以外の値は全て0〜1で受け取る。並びがOSCで送る値の順番になる
	SynthDef(\clicks, { |out, rate = 0, irregularity = 0, brightness = 0, amp = 0|
		var clickRate = smooth.(rate).linexp(0, 1, minRate, maxFreq);
		var smoothedIrregularity = smooth.(irregularity);
		var clickFreq = smooth.(brightness).linexp(0, 1, minFreq, maxFreq);
		var volume = ampToGain.(smooth.(amp));
		// 他の層と同じ実効値に揃える。不規則なクリックも平均の頻度は同じため、同じ倍率にする
		// 揃える実効値に届かないまばらなクリックは、1回の揺れの山(約0.7)が出力の上限(main.scdのlimiterLevel)に近く大きくできないため、そのまま鳴らす
		var clickGain = (layerRms / clickTrainRms.(clickRate, clickFreq)).min(1);
		var click = { |trigger|
			// 鳴るたびに揺れを最初から始め、クリックごとに音の形が変わらないようにする
			// 値0から始め、鳴った瞬間の跳びで全ての周波数を含むパチッという音が混ざり、明るさの違いが埋もれないようにする
			var wave = sin(Sweep.ar(trigger, clickFreq) * 2pi);
			// 頻度が高く前のクリックが鳴り終わらないうちに次が来ても、足し合わさらず鳴り直すようにする
			wave * EnvGen.ar(Env.perc(0, clickCycles / clickFreq, curve: envelopeCurve), trigger);
		};
		var regularClicks = click.(Impulse.ar(clickRate));
		// Dustはクリックごとに音量がランダムになるため、鳴ったかどうかだけを使い、不規則さが音量に混ざらないようにする
		var randomClicks = click.(Dust.ar(clickRate) > 0);
		var mixed = (regularClicks * (1 - smoothedIrregularity)) + (randomClicks * smoothedIrregularity);
		// 揺れの周波数か頻度のどちらかが高ければ、高い音として聴こえる
		Out.ar(out, mixed * clickGain * freqGain.(max(clickFreq, clickRate)) * volume ! 2);
	});
}
