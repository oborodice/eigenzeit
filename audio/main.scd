(
// 各層のファイルはこのファイルと同じ場所から読み込む。起動を待つ間は実行中のファイルの場所が取れないため、先に控えておく
var directory = thisProcess.nowExecutingPath.dirname;
// 各層のファイルと、そこから作るSynthの数。2つ以上作る層は、OSCのアドレスに1からの番号を付ける(/sines/1、/sines/2)
// サイン波は、低い所のうなりと鋭く高い音を同時に鳴らせるよう2つにする。どちらも全範囲を使い、組み合わせ方はAIが選ぶ
var layers = [
	(fileName: "sines.scd", synthCount: 2),
	(fileName: "clicks.scd", synthCount: 1),
	(fileName: "noise.scd", synthCount: 1),
];
// 新しい値へは、この時間をかけて一定の速さで移る
// 値が一瞬で跳ぶと波の形が途切れ、プツッという音が耳やツイーターの負担になるため、少なくとも数十ミリ秒はかける
// それより長いのは、一瞬では変われない生き物の体のような性質を、AIの体に持たせるため
// AIが音を選び直す間隔より短くし、移り終わってから観測できるようにする
var transitionSeconds = 2;
// 下限はHS5が出せる低さ、上限は人間に聞こえる範囲の上限に合わせる。耳は周波数の比で高さを感じるため、対数で対応付ける
// 下限は聴きやすくするための調整ではなく、出せない低さを無理に鳴らしてウーファーを傷めないための制限である
var minFreq = 55;
var maxFreq = 20000;
// 聞こえにくい高い音でも、大きな音量では耳を疲れさせるため、この周波数より上は音量を下げる
// 聴きやすくするための調整ではなく、耳を傷めないための制限であり、人間に合わせて出力を丸めることにはならない
var highFreqStart = 8000;
var highFreqMinGain = 0.25;
// 高い音ほど小さく鳴る体にする。声帯や叩いた物のような物理的な体は、高い周波数ほど弱くしか音を出せず、自然の音の多くは1オクターブ上がるごとに3dBほど弱くなる
// 人間に聴きやすくするための調整ではなく、移る速さと同じく、AIの体の性質として固定する。AIは高い音も選べ、小さく鳴ることも含めて学ぶ
// 入れたきっかけは、乱数で鳴らすと高い音がいつも目立って聴こえたこと
// 低い側は持ち上げず、この周波数より上だけを下げる。始まりの周波数は鳴らして決め直す
var tiltStartFreq = 1000;
var tiltDbPerOctave = -3;
// 音量の下限(dB)。最大の音量をどこに合わせても、静かな部屋の物音より小さくなる幅にする
var minAmpDb = -60;
// 層を足し合わせると音量の値の上限を超えるため、音割れしないよう少し余裕を持たせた上限に抑える
var limiterLevel = 0.9;
var pythonAddress = NetAddr("127.0.0.1", 9000);

// 0〜1のまま滑らかにしてから実際の値に直し、周波数の高さによって動きの速さが変わって聴こえないようにする
// lagは指数的に近づき、最初の1秒ほどで大半が動いてしまうため、一定の速さで移るVarLagを使う
var smooth = { |value| VarLag.kr(value.clip(0, 1), transitionSeconds) };
var highFreqGain = { |freq| freq.explin(highFreqStart, maxFreq, 1, highFreqMinGain) };
var tiltGain = { |freq| ((freq.max(tiltStartFreq) / tiltStartFreq).log2 * tiltDbPerOctave).dbamp };
// 理由の違う2つの制限を、周波数ごとの音量の倍率として1つにまとめて各層に渡す
var freqGain = { |freq| tiltGain.(freq) * highFreqGain.(freq) };
// 音量の0〜1は、dBに対応させる。耳は音の大きさも比で感じるため、0〜1を均等に分けた区画が、耳にとっても均等になる
// 0で無音になり、全ての層を0にして無音を表せるよう、下限のdBの振幅を差し引き、1で1に戻るよう割り直す
var ampToGain = { |amp| (amp.linlin(0, 1, minAmpDb, 0).dbamp - minAmpDb.dbamp) / (1 - minAmpDb.dbamp) };

// 各層のファイルは、共通の値と処理を受け取ってSynthDefを作る関数を返す(ファイルの最後の値が戻り値になる)
var layerSynthDefs = layers.collect { |layer|
	var makeSynthDef = thisProcess.interpreter.executeFile(directory +/+ layer.fileName);
	makeSynthDef.(smooth, ampToGain, freqGain, minFreq, maxFreq);
};
var mic = thisProcess.interpreter.executeFile(directory +/+ "mic.scd");

// マイクの最も高い帯域(20kHz)の上の端は約22.4kHzで、扱える周波数の上限(サンプリング周波数の半分)を超えないよう48kHzにする
s.options.sampleRate = 48000;

s.waitForBoot {
	var mixBus = Bus.audio(s, 2);

	layerSynthDefs.do(_.add);
	mic.synthDef.add;
	SynthDef(\output, {
		Out.ar(0, Limiter.ar(In.ar(mixBus, 2), limiterLevel));
	}).add;

	// SynthDefの登録はサーバー側で後から行われるため、終わるのを待ってから鳴らす
	s.sync;

	// 各層より後に計算されるよう、末尾に置く(各層は先頭に置かれる)
	Synth.tail(s, \output);

	layers.do { |layer, layerIndex|
		var synthDef = layerSynthDefs[layerIndex];
		// OSCの値は、SynthDefの引数の並び(書き出し先のoutを除く)の順に割り当て、順番を書く場所を1か所にする
		var paramNames = synthDef.allControlNames.collect(_.name).reject(_ == \out);
		layer.synthCount.do { |synthIndex|
			var synth = Synth(synthDef.name, [\out, mixBus]);
			var suffix = if(layer.synthCount > 1, { "/" ++ (synthIndex + 1) }, { "" });
			var address = ("/" ++ synthDef.name ++ suffix).asSymbol;
			OSCdef(address, { |msg|
				// msgの0番目はアドレスのため、値は1番目から
				synth.set(*paramNames.collect { |name, paramIndex| [name, msg[paramIndex + 1]] }.flatten);
			}, address);
		};
	};

	Synth(mic.synthDef.name);
	// msgの1、2番目はSynthの番号と識別用の番号のため、値は3番目から
	OSCdef(mic.synthDef.name, { |msg|
		pythonAddress.sendMsg(msg[0], mic.toJson(msg[3..]));
	}, ("/" ++ mic.synthDef.name).asSymbol, s.addr);
};
)
