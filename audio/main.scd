(
// 各層のファイルはこのファイルと同じ場所から読み込む。起動を待つ間は実行中のファイルの場所が取れないため、先に控えておく
var directory = thisProcess.nowExecutingPath.dirname;
// 各層のファイルと、そこから作るSynthの数。2つ以上作る層は、OSCのアドレスに1からの番号を付ける(/sines/1、/sines/2)
// サイン波は、低い所のうなりと鋭く高い音を同時に鳴らせるよう2つにする。どちらも全範囲を使い、組み合わせ方はAIが選ぶ
var layers = [(fileName: "sines.scd", synthCount: 2), (fileName: "clicks.scd", synthCount: 1)];
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
// 層を足し合わせると音量の値の上限を超えるため、音割れしないよう少し余裕を持たせた上限に抑える
var limiterLevel = 0.9;

// 0〜1のまま滑らかにしてから実際の値に直し、周波数の高さによって動きの速さが変わって聴こえないようにする
// lagは指数的に近づき、最初の1秒ほどで大半が動いてしまうため、一定の速さで移るVarLagを使う
var smooth = { |value| VarLag.kr(value.clip(0, 1), transitionSeconds) };
var highFreqGain = { |freq| freq.explin(highFreqStart, maxFreq, 1, highFreqMinGain) };

// 各層のファイルは、共通の値と処理を受け取ってSynthDefを作る関数を返す(ファイルの最後の値が戻り値になる)
var layerSynthDefs = layers.collect { |layer|
	var makeSynthDef = thisProcess.interpreter.executeFile(directory +/+ layer.fileName);
	makeSynthDef.(smooth, highFreqGain, minFreq, maxFreq);
};

s.waitForBoot {
	// 各層はここに書き出し、最後にまとめて上限を抑えてから出力する
	var mixBus = Bus.audio(s, 2);

	layerSynthDefs.do(_.add);
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
			// 2つ以上作る層だけ、アドレスに1からの番号を付ける
			var suffix = if(layer.synthCount > 1, { "/" ++ (synthIndex + 1) }, { "" });
			var address = ("/" ++ synthDef.name ++ suffix).asSymbol;
			OSCdef(address, { |msg|
				// msgの0番目はアドレスのため、値は1番目から
				synth.set(*paramNames.collect { |name, paramIndex| [name, msg[paramIndex + 1]] }.flatten);
			}, address);
		};
	};
};
)
