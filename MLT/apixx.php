<?php
// content moved to /API.PHP

/*
ini_set("assert.warning", "1");
ini_set("display_errors", "1");

$data = json_decode(file_get_contents("meta.json"));
$randPos = array();
//          1 2 3 4 5 6 7 8 9 A B
$ranVals = [0,0,0,0,1,1,1,1,1,0,0];
$response = array();


while (count($randPos)<10) {
    $x = rand(0,count($data)-1);
    if (in_array($x, $randPos)==false) {
        $item = $data[$x];        
        if ($ranVals[$item->num_sounds_without_noise]<2) {
            $randPos[]=$x;                
            $response[]= $item;
            $item->answer1 = null;
            $item->answer2 = null;
            $item->answer3 = null;
            $item->answerAvg = null;
            $ranVals[$item->num_sounds_without_noise]++;
        }
    }
}

die(json_encode($response));
*/
?>

